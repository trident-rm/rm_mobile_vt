/* D3-0 probe: stateful meson-vdec HEVC decode -> NV12M CAPTURE dmabuf -> DRM/KMS overlay.
 *
 * Purpose: prove that the *decoded* V4L2 CAPTURE buffers (not a test pattern)
 * can be exported with VIDIOC_EXPBUF, imported with PRIME_FD_TO_HANDLE and
 * scanned out on the meson overlay plane, with a buffer lifecycle that cannot
 * overwrite a frame still held by scanout.
 *
 * Deliberately minimal:
 *   - file input only, no USB, no Python, no ffmpeg
 *   - one frame at a time, blocking legacy SETPLANE (returns after vblank),
 *     so the *previous* buffer is safe to re-queue
 *   - no EOF drain (EOF handling is a known separate defect)
 *
 * Modes:
 *   --inventory                 read-only capability dump (no DRM master)
 *   --file PATH [--bytes N] [--frames N] [--dump DIR]
 *   --no-display                decode-only (DQBUF -> QBUF immediately)
 *
 * Build (CM311, raw ioctls, no libdrm link needed):
 *   gcc -O2 -Wall -Wextra -o build/d3/d3_probe tools/d3_probe.c
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#include <drm/drm.h>
#include <drm/drm_mode.h>

#define FOURCC(a, b, c, d) ((uint32_t)(a) | ((uint32_t)(b) << 8) | ((uint32_t)(c) << 16) | ((uint32_t)(d) << 24))
#define MAX_CAP_BUFS 24
#define MAX_OUT_BUFS 8
#define MAX_PLANES 2
#define AU_MAX_BYTES (512 * 1024)
#define AU_MAGIC 0x44574155u /* "DWAU" */
#define AU_FLAG_IRAP 1u
#define AU_FLAG_EOS 2u

struct au_hdr {
    uint32_t magic;
    uint32_t len;
    uint32_t seq;
    uint32_t flags;
    uint64_t ts_ns;
} __attribute__((packed));

static volatile sig_atomic_t g_stop = 0;

static void on_signal(int sig) { (void)sig; g_stop = 1; }

static int xioctl(int fd, unsigned long req, void *arg) {
    int rc;
    do {
        rc = ioctl(fd, req, arg);
    } while (rc < 0 && errno == EINTR);
    return rc;
}

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

static uint64_t mono_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

#define MAX_FED 32
#define MAX_AGE_SAMPLES 512

struct fed_au {
    uint32_t seq;
    uint64_t send_ns;
    uint64_t recv_ns;
};

struct out_buf {
    void *addr;
    size_t len;
    size_t used;
};

struct cap_buf {
    int dmabuf[MAX_PLANES];
    uint32_t handle[MAX_PLANES];
    uint32_t fb_id;
    void *map[MAX_PLANES];
    size_t maplen[MAX_PLANES];
    unsigned int queued;
};

struct held_fb {
    int active;
    int dmabuf[2];
    uint32_t handle[2];
    uint32_t fb_id;
    void *map[2];
    size_t maplen[2];
};

struct ctx {
    int video_fd;
    int card_fd;
    int master;
    uint32_t plane_id;
    uint32_t primary_id;
    uint32_t crtc_id;
    uint32_t conn_id;
    uint32_t disp_w, disp_h;
    uint32_t video_w, video_h;
    uint32_t bpl[MAX_PLANES];
    uint32_t plane_size[MAX_PLANES];
    uint32_t num_cap;
    struct out_buf out[8];
    unsigned int num_out;
    const unsigned char *in_data;
    size_t in_len;
    size_t *chunk_off;
    size_t *chunk_len;
    size_t n_chunks;
    size_t next_chunk;
    int sock_fd;
    int out_free[MAX_OUT_BUFS];
    int n_out_free;
    struct cap_buf cap[MAX_CAP_BUFS];
    unsigned int primary_crtc_id, primary_fb_id;
    uint32_t last_fb;
    int last_idx;
    const char *dump_dir;
    int dump_frames;
    const char *dump_recover_dir;
    int rec_dumps;
    int rec_dump_max;
    int rec_active;
    int held_dumped;
    int held_release_countdown;
    const char *dump_first_dir;
    int first_dumps;
    int first_dump_max;
    int hide_primary;
    int primary_hidden;
    int recover_sleep_ms;
    int recv_buf_kb;
    int start_gate;
    int gate_frames;
    int gate_open;
    unsigned gated_frames;
    int cap_bufs;
    int want_mode;
    unsigned want_w, want_h, want_hz;
    struct drm_mode_modeinfo orig_mode;
    int orig_mode_valid;
    uint32_t orig_fb;
    int mode_changed;
    int recovering;
    double recover_start_ms;
    /* Latency instrumentation (opt-in --lat-csv). All clocks are
     * CLOCK_MONOTONIC, matching the sender's ts_ns in the AU header. */
    FILE *lat_fp;
    int have_last_present;
    double last_present_ms;
    int have_recover_last_present;
    double recover_last_present_ms;
    struct fed_au fed[MAX_FED];
    int fed_head, fed_tail;
    uint32_t last_pop_seq;
    int have_pop_seq;
    unsigned seq_gaps;
    double age_ms[MAX_AGE_SAMPLES];
    int age_n;
    int backlog_max;
    struct held_fb held[2];
    int held_n;
    int prev_idx;
};

static void ctx_init(struct ctx *c) {
    memset(c, 0, sizeof(*c));
    c->video_fd = -1;
    c->card_fd = -1;
    c->sock_fd = -1;
    c->last_idx = -1;
    c->prev_idx = -1;
    c->video_w = 1920;
    c->video_h = 1080;
    c->cap_bufs = 0;
    for (unsigned int i = 0; i < MAX_CAP_BUFS; i++) {
        c->cap[i].dmabuf[0] = c->cap[i].dmabuf[1] = -1;
    }
    for (unsigned int i = 0; i < 2; i++)
        c->held[i].dmabuf[0] = c->held[i].dmabuf[1] = -1;
}

/* ---------------- read-only inventory ---------------- */

static void inventory(void) {
    char path[64];
    for (int i = 0; i < 4; i++) {
        snprintf(path, sizeof(path), "/dev/video%d", i);
        int fd = open(path, O_RDWR | O_NONBLOCK);
        if (fd < 0) continue;
        printf("=== %s ===\n", path);
        struct v4l2_capability cap;
        memset(&cap, 0, sizeof(cap));
        if (xioctl(fd, VIDIOC_QUERYCAP, &cap) == 0)
            printf("driver=%s card=%s caps=0x%08x device_caps=0x%08x\n",
                   cap.driver, cap.card, cap.capabilities, cap.device_caps);

        for (int dir = 0; dir < 2; dir++) {
            uint32_t type = dir ? V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE
                                : V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
            struct v4l2_fmtdesc d;
            memset(&d, 0, sizeof(d));
            d.type = type;
            printf("%s formats:\n", dir ? "CAPTURE" : "OUTPUT");
            for (d.index = 0; xioctl(fd, VIDIOC_ENUM_FMT, &d) == 0; d.index++) {
                printf("  [%u] %.4s %s flags=0x%x\n", d.index,
                       (const char *)&d.pixelformat, d.description, d.flags);
            }
            struct v4l2_format f;
            memset(&f, 0, sizeof(f));
            f.type = type;
            if (xioctl(fd, VIDIOC_G_FMT, &f) == 0) {
                printf("  G_FMT %ux%u %.4s planes=%u",
                       f.fmt.pix_mp.width, f.fmt.pix_mp.height,
                       (const char *)&f.fmt.pix_mp.pixelformat,
                       f.fmt.pix_mp.num_planes);
                for (unsigned int p = 0; p < f.fmt.pix_mp.num_planes; p++)
                    printf(" [p%u bpl=%u size=%u]", p,
                           f.fmt.pix_mp.plane_fmt[p].bytesperline,
                           f.fmt.pix_mp.plane_fmt[p].sizeimage);
                printf("\n");
            }
        }
        struct v4l2_control ctl;
        memset(&ctl, 0, sizeof(ctl));
        ctl.id = V4L2_CID_MIN_BUFFERS_FOR_CAPTURE;
        if (xioctl(fd, VIDIOC_G_CTRL, &ctl) == 0)
            printf("min_buffers_for_capture=%d (pre-stream default)\n", ctl.value);
        close(fd);
    }

    int dfd = open("/dev/dri/card0", O_RDWR);
    if (dfd < 0) { perror("open /dev/dri/card0"); return; }
    struct drm_set_client_cap cap = { .capability = DRM_CLIENT_CAP_UNIVERSAL_PLANES, .value = 1 };
    xioctl(dfd, DRM_IOCTL_SET_CLIENT_CAP, &cap);
    struct drm_mode_card_res res;
    memset(&res, 0, sizeof(res));
    if (xioctl(dfd, DRM_IOCTL_MODE_GETRESOURCES, &res) < 0) { perror("GETRESOURCES"); close(dfd); return; }
    uint32_t *conns = calloc(res.count_connectors ? res.count_connectors : 1, sizeof(uint32_t));
    uint32_t *crtcs = calloc(res.count_crtcs ? res.count_crtcs : 1, sizeof(uint32_t));
    uint32_t *planes = NULL;
    uint32_t n_fbs = res.count_fbs;
    res.connector_id_ptr = (uint64_t)(uintptr_t)conns;
    res.crtc_id_ptr = (uint64_t)(uintptr_t)crtcs;
    res.count_fbs = 0;      /* fb_id_ptr is NULL */
    res.count_encoders = 0; /* encoder_id_ptr is NULL */
    if (xioctl(dfd, DRM_IOCTL_MODE_GETRESOURCES, &res) < 0) { perror("GETRESOURCES2"); goto out; }

    struct drm_mode_get_plane_res pr;
    memset(&pr, 0, sizeof(pr));
    if (xioctl(dfd, DRM_IOCTL_MODE_GETPLANERESOURCES, &pr) < 0) { perror("GETPLANERESOURCES"); goto out; }
    planes = calloc(pr.count_planes ? pr.count_planes : 1, sizeof(uint32_t));
    pr.plane_id_ptr = (uint64_t)(uintptr_t)planes;
    if (xioctl(dfd, DRM_IOCTL_MODE_GETPLANERESOURCES, &pr) < 0) { perror("GETPLANERESOURCES2"); goto out; }
    printf("=== DRM ===\nconnectors=%u crtcs=%u planes=%u fbs=%u\n",
           res.count_connectors, res.count_crtcs, pr.count_planes, n_fbs);

    for (uint32_t i = 0; i < res.count_connectors; i++) {
        struct drm_mode_get_connector gc;
        memset(&gc, 0, sizeof(gc));
        gc.connector_id = conns[i];
        if (xioctl(dfd, DRM_IOCTL_MODE_GETCONNECTOR, &gc) < 0) continue;
        uint32_t nmodes = gc.count_modes, nenc = gc.count_encoders;
        struct drm_mode_modeinfo *modes = calloc(nmodes ? nmodes : 1, sizeof(*modes));
        uint32_t *enc = calloc(nenc ? nenc : 1, sizeof(uint32_t));
        gc.modes_ptr = (uint64_t)(uintptr_t)modes;
        gc.encoders_ptr = (uint64_t)(uintptr_t)enc;
        if (xioctl(dfd, DRM_IOCTL_MODE_GETCONNECTOR, &gc) == 0) {
            printf("connector %u status=%u modes=%u encoder=%u\n",
                   conns[i], gc.connection, nmodes, gc.encoder_id);
            for (uint32_t k = 0; k < nmodes && k < 4; k++)
                printf("  mode %s %ux%u clock=%u type=0x%x\n", modes[k].name,
                       modes[k].hdisplay, modes[k].vdisplay, modes[k].clock, modes[k].type);
        }
        free(modes);
        free(enc);
    }
    for (uint32_t i = 0; i < res.count_crtcs; i++) {
        struct drm_mode_crtc crtc;
        memset(&crtc, 0, sizeof(crtc));
        crtc.crtc_id = crtcs[i];
        if (xioctl(dfd, DRM_IOCTL_MODE_GETCRTC, &crtc) == 0)
            printf("crtc %u mode_valid=%u fb=%u %ux%u\n", crtcs[i], crtc.mode_valid,
                   crtc.fb_id, crtc.mode.hdisplay, crtc.mode.vdisplay);
    }
    for (uint32_t i = 0; i < pr.count_planes; i++) {
        struct drm_mode_get_plane p;
        memset(&p, 0, sizeof(p));
        p.plane_id = planes[i];
        if (xioctl(dfd, DRM_IOCTL_MODE_GETPLANE, &p) < 0) continue;
        uint32_t nf = p.count_format_types;
        uint32_t *fmts = calloc(nf ? nf : 1, sizeof(uint32_t));
        p.format_type_ptr = (uint64_t)(uintptr_t)fmts;
        if (xioctl(dfd, DRM_IOCTL_MODE_GETPLANE, &p) == 0) {
            printf("plane %u crtc=%u fb=%u possible_crtcs=0x%x formats:", planes[i],
                   p.crtc_id, p.fb_id, p.possible_crtcs);
            for (uint32_t k = 0; k < nf; k++)
                printf(" %.4s", (const char *)&fmts[k]);
            printf("\n");
        }
        free(fmts);
    }
out:
    free(conns);
    free(crtcs);
    free(planes);
    close(dfd);
}

/* ---------------- DRM setup ---------------- */

static uint32_t find_nv12_plane(int fd, uint32_t *primary_out) {
    struct drm_mode_get_plane_res pr;
    memset(&pr, 0, sizeof(pr));
    if (xioctl(fd, DRM_IOCTL_MODE_GETPLANERESOURCES, &pr) < 0) return 0;
    uint32_t *planes = calloc(pr.count_planes ? pr.count_planes : 1, sizeof(uint32_t));
    pr.plane_id_ptr = (uint64_t)(uintptr_t)planes;
    if (xioctl(fd, DRM_IOCTL_MODE_GETPLANERESOURCES, &pr) < 0) { free(planes); return 0; }
    uint32_t chosen = 0, primary = 0;
    for (uint32_t i = 0; i < pr.count_planes; i++) {
        struct drm_mode_get_plane p;
        memset(&p, 0, sizeof(p));
        p.plane_id = planes[i];
        if (xioctl(fd, DRM_IOCTL_MODE_GETPLANE, &p) < 0) continue;
        uint32_t nf = p.count_format_types;
        uint32_t *fmts = calloc(nf ? nf : 1, sizeof(uint32_t));
        p.format_type_ptr = (uint64_t)(uintptr_t)fmts;
        int has_nv12 = 0;
        if (xioctl(fd, DRM_IOCTL_MODE_GETPLANE, &p) == 0) {
            for (uint32_t k = 0; k < nf; k++)
                if (fmts[k] == FOURCC('N', 'V', '1', '2')) has_nv12 = 1;
        }
        free(fmts);
        if (has_nv12 && !chosen) chosen = planes[i];
        /* The fbcon plane is the one currently bound to a CRTC with a fb and
         * is not the NV12 plane. Used only by --hide-primary. */
        if (!has_nv12 && p.fb_id && p.crtc_id && planes[i] != chosen) primary = planes[i];
    }
    *primary_out = primary;
    free(planes);
    return chosen;
}

static int drm_setup(struct ctx *c) {
    c->card_fd = open("/dev/dri/card0", O_RDWR);
    if (c->card_fd < 0) { perror("open /dev/dri/card0"); return -1; }
    for (int i = 0; i < 20; i++) {
        if (xioctl(c->card_fd, DRM_IOCTL_SET_MASTER, 0) == 0) { c->master = 1; break; }
        usleep(100000);
    }
    if (!c->master) { perror("SET_MASTER"); return -1; }

    struct drm_set_client_cap cap = { .capability = DRM_CLIENT_CAP_UNIVERSAL_PLANES, .value = 1 };
    if (xioctl(c->card_fd, DRM_IOCTL_SET_CLIENT_CAP, &cap) < 0) { perror("SET_CLIENT_CAP"); return -1; }

    c->plane_id = find_nv12_plane(c->card_fd, &c->primary_id);
    if (!c->plane_id) { fprintf(stderr, "no NV12 DRM plane\n"); return -1; }

    struct drm_mode_card_res res;
    memset(&res, 0, sizeof(res));
    if (xioctl(c->card_fd, DRM_IOCTL_MODE_GETRESOURCES, &res) < 0) { perror("GETRESOURCES"); return -1; }
    uint32_t *conns = calloc(res.count_connectors ? res.count_connectors : 1, sizeof(uint32_t));
    res.connector_id_ptr = (uint64_t)(uintptr_t)conns;
    res.count_crtcs = 0;     /* crtc_id_ptr is NULL */
    res.count_fbs = 0;       /* fb_id_ptr is NULL */
    res.count_encoders = 0;  /* encoder_id_ptr is NULL */
    if (xioctl(c->card_fd, DRM_IOCTL_MODE_GETRESOURCES, &res) < 0) { free(conns); return -1; }
    for (uint32_t i = 0; i < res.count_connectors; i++) {
        struct drm_mode_get_connector gc;
        memset(&gc, 0, sizeof(gc));
        gc.connector_id = conns[i];
        if (xioctl(c->card_fd, DRM_IOCTL_MODE_GETCONNECTOR, &gc) < 0) continue;
        if (gc.connection != 1) continue;
        uint32_t nenc = gc.count_encoders;
        uint32_t *enc = calloc(nenc ? nenc : 1, sizeof(uint32_t));
        gc.encoders_ptr = (uint64_t)(uintptr_t)enc;
        gc.count_modes = 0; /* modes_ptr is NULL */
        gc.count_props = 0; /* props_ptr is NULL */
        if (xioctl(c->card_fd, DRM_IOCTL_MODE_GETCONNECTOR, &gc) < 0) { free(enc); continue; }
        if (nenc && enc[0]) {
            struct drm_mode_get_encoder ge;
            memset(&ge, 0, sizeof(ge));
            ge.encoder_id = enc[0];
            if (xioctl(c->card_fd, DRM_IOCTL_MODE_GETENCODER, &ge) == 0)
                c->crtc_id = ge.crtc_id;
        }
        c->conn_id = conns[i];
        free(enc);
        if (c->crtc_id) break;
    }
    free(conns);
    if (!c->crtc_id) { fprintf(stderr, "no connected connector with CRTC\n"); return -1; }

    struct drm_mode_crtc crtc;
    memset(&crtc, 0, sizeof(crtc));
    crtc.crtc_id = c->crtc_id;
    if (xioctl(c->card_fd, DRM_IOCTL_MODE_GETCRTC, &crtc) < 0) { perror("GETCRTC"); return -1; }
    if (!crtc.mode_valid) {
        fprintf(stderr, "CRTC has no active mode; D3-0 refuses to change modes\n");
        return -1;
    }
    c->disp_w = crtc.mode.hdisplay;
    c->disp_h = crtc.mode.vdisplay;
    c->orig_mode = crtc.mode;
    c->orig_mode_valid = crtc.mode_valid;
    c->orig_fb = crtc.fb_id;
    if (c->want_mode) {
        struct drm_mode_get_connector gc;
        memset(&gc, 0, sizeof(gc));
        gc.connector_id = c->conn_id;
        if (xioctl(c->card_fd, DRM_IOCTL_MODE_GETCONNECTOR, &gc) < 0) { perror("GETCONNECTOR"); return -1; }
        uint32_t nmodes = gc.count_modes;
        struct drm_mode_modeinfo *modes = calloc(nmodes ? nmodes : 1, sizeof(*modes));
        gc.modes_ptr = (uint64_t)(uintptr_t)modes;
        gc.count_encoders = 0;
        gc.count_props = 0;
        if (xioctl(c->card_fd, DRM_IOCTL_MODE_GETCONNECTOR, &gc) < 0) { free(modes); return -1; }
        int found = -1;
        for (uint32_t k = 0; k < nmodes; k++) {
            if (modes[k].hdisplay != c->want_w || modes[k].vdisplay != c->want_h) continue;
            unsigned hz = modes[k].vrefresh;
            if (!hz && modes[k].htotal && modes[k].vtotal)
                hz = (unsigned)((modes[k].clock * 1000ULL) / ((uint64_t)modes[k].htotal * modes[k].vtotal));
            int diff = (int)hz - (int)c->want_hz;
            if (diff < 0) diff = -diff;
            if (diff <= 2) { found = (int)k; break; }
        }
        if (found < 0) {
            fprintf(stderr, "requested mode %ux%u@%u not found; available %ux%u:",
                    c->want_w, c->want_h, c->want_hz, c->want_w, c->want_h);
            for (uint32_t k = 0; k < nmodes; k++) {
                if (modes[k].hdisplay == c->want_w && modes[k].vdisplay == c->want_h)
                    fprintf(stderr, " %uHz", modes[k].vrefresh);
            }
            fprintf(stderr, "\n");
            free(modes);
            return -1;
        }
        struct drm_mode_crtc sc;
        memset(&sc, 0, sizeof(sc));
        sc.crtc_id = c->crtc_id;
        sc.fb_id = c->orig_fb;
        sc.set_connectors_ptr = (uint64_t)(uintptr_t)&c->conn_id;
        sc.count_connectors = 1;
        sc.mode = modes[found];
        sc.mode_valid = 1;
        if (xioctl(c->card_fd, DRM_IOCTL_MODE_SETCRTC, &sc) < 0) {
            perror("SETCRTC(mode)");
            free(modes);
            return -1;
        }
        c->mode_changed = 1;
        c->disp_w = modes[found].hdisplay;
        c->disp_h = modes[found].vdisplay;
        printf("mode set: %s %ux%u %uHz (was %ux%u)\n", modes[found].name,
               modes[found].hdisplay, modes[found].vdisplay, modes[found].vrefresh,
               c->orig_mode.hdisplay, c->orig_mode.vdisplay);
        free(modes);
    }
    c->primary_crtc_id = 0;
    c->primary_fb_id = 0;
    if (c->primary_id) {
        struct drm_mode_get_plane p;
        memset(&p, 0, sizeof(p));
        p.plane_id = c->primary_id;
        if (xioctl(c->card_fd, DRM_IOCTL_MODE_GETPLANE, &p) == 0) {
            c->primary_crtc_id = p.crtc_id;
            c->primary_fb_id = p.fb_id;
        }
    }
    printf("drm: crtc=%u plane=%u primary=%u display=%ux%u primary_fb=%u\n",
           c->crtc_id, c->plane_id, c->primary_id, c->disp_w, c->disp_h, c->primary_fb_id);
    return 0;
}

static void drm_hide_primary(struct ctx *c) {
    if (!c->primary_id || !c->primary_fb_id || !c->primary_crtc_id) return;
    struct drm_mode_set_plane sp;
    memset(&sp, 0, sizeof(sp));
    sp.plane_id = c->primary_id;
    sp.crtc_id = c->primary_crtc_id;
    sp.fb_id = 0;
    if (xioctl(c->card_fd, DRM_IOCTL_MODE_SETPLANE, &sp) == 0)
        printf("primary plane %u disabled (restored by master drop)\n", c->primary_id);
    else
        perror("SETPLANE(primary,0)");
}

static void held_release(struct ctx *c);
static int dump_planes(const char *path, const uint8_t *y, const uint8_t *uv,
                       uint32_t w, uint32_t h, uint32_t bpl0, uint32_t bpl1);

static int drm_present(struct ctx *c, int idx) {
    if (!c->cap[idx].fb_id) return -1;
    /* Hide the console only when the first video frame is ready; hiding it at
     * startup leaves no active plane and the CRTC shows its green background. */
    if (c->hide_primary && !c->primary_hidden) {
        drm_hide_primary(c);
        c->primary_hidden = 1;
    }
    /* Release the previous session's held frame only after several presents
     * have elapsed: the meson flip can take effect one or two frames later,
     * and freeing the UV plane while it is still scanned shows a green
     * curtain. */
    if (c->held_n > 0 && c->held_release_countdown > 0) {
        if (--c->held_release_countdown == 0) held_release(c);
    }
    struct drm_mode_set_plane sp;
    memset(&sp, 0, sizeof(sp));
    sp.plane_id = c->plane_id;
    sp.crtc_id = c->crtc_id;
    sp.fb_id = c->cap[idx].fb_id;
    sp.crtc_x = 0;
    sp.crtc_y = 0;
    sp.crtc_w = c->video_w <= c->disp_w ? c->video_w : c->disp_w;
    sp.crtc_h = c->video_h <= c->disp_h ? c->video_h : c->disp_h;
    sp.src_x = 0;
    sp.src_y = 0;
    sp.src_w = c->video_w << 16;
    sp.src_h = c->video_h << 16;
    /* Blocking commit: on return the previous scanout buffer is released. */
    if (xioctl(c->card_fd, DRM_IOCTL_MODE_SETPLANE, &sp) < 0) { perror("SETPLANE"); return -1; }
    if (c->dump_recover_dir && c->have_recover_last_present && c->held_n > 0 &&
        !c->held_dumped && c->held[0].map[0] && c->held[0].map[1]) {
        char path[512];
        c->held_dumped = 1;
        snprintf(path, sizeof(path), "%s/held_%.1f_%ux%u.yuv", c->dump_recover_dir,
                 now_ms(), c->video_w, c->video_h);
        dump_planes(path, c->held[0].map[0], c->held[0].map[1],
                    c->video_w, c->video_h, c->bpl[0], c->bpl[1]);
    }
    if (c->held_n > 0 && c->held_release_countdown == 0)
        c->held_release_countdown = 5;
    return 0;
}

/* ---------------- V4L2 ---------------- */

static int read_file(const char *path, unsigned char **data, size_t *len, size_t limit) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) { perror(path); return -1; }
    struct stat st;
    if (fstat(fd, &st) < 0) { perror("fstat"); close(fd); return -1; }
    size_t n = (size_t)st.st_size;
    if (limit && n > limit) n = limit;
    unsigned char *buf = malloc(n ? n : 1);
    if (!buf) { close(fd); return -1; }
    size_t got = 0;
    while (got < n) {
        ssize_t r = read(fd, buf + got, n - got);
        if (r < 0) { if (errno == EINTR) continue; perror("read"); free(buf); close(fd); return -1; }
        if (r == 0) break;
        got += (size_t)r;
    }
    close(fd);
    *data = buf;
    *len = got;
    return 0;
}

struct nal_info {
    size_t off;
    size_t len;
    unsigned type;
    unsigned first_slice;
};

static int split_annexb(const unsigned char *d, size_t n, size_t **offs,
                        size_t **lens, size_t *count) {
    size_t ncap = 512, nnals = 0;
    struct nal_info *na = malloc(ncap * sizeof(*na));
    if (!na) return -1;

    size_t start = SIZE_MAX;
    for (size_t i = 0; i + 3 < n; ) {
        size_t sc = 0;
        if (d[i] == 0 && d[i + 1] == 0 && d[i + 2] == 1) sc = 3;
        else if (d[i] == 0 && d[i + 1] == 0 && d[i + 2] == 0 && d[i + 3] == 1) sc = 4;
        if (!sc) { i++; continue; }
        if (start != SIZE_MAX) {
            if (nnals == ncap) {
                ncap *= 2;
                struct nal_info *nn = realloc(na, ncap * sizeof(*na));
                if (!nn) { free(na); return -1; }
                na = nn;
            }
            size_t hdr = start + (d[start + 2] == 1 ? 3 : 4);
            na[nnals].off = start;
            na[nnals].len = i - start;
            na[nnals].type = (hdr + 1 < n) ? ((d[hdr] >> 1) & 0x3f) : 63;
            na[nnals].first_slice = 0;
            if (na[nnals].type <= 31 && hdr + 2 < n)
                na[nnals].first_slice = (d[hdr + 2] & 0x80) != 0;
            nnals++;
        }
        start = i;
        i += sc;
    }
    if (start != SIZE_MAX && start < n) {
        if (nnals == ncap) {
            ncap++;
            struct nal_info *nn = realloc(na, ncap * sizeof(*na));
            if (!nn) { free(na); return -1; }
            na = nn;
        }
        size_t hdr = start + (d[start + 2] == 1 ? 3 : 4);
        na[nnals].off = start;
        na[nnals].len = n - start;
        na[nnals].type = (hdr + 1 < n) ? ((d[hdr] >> 1) & 0x3f) : 63;
        na[nnals].first_slice = 0;
        if (na[nnals].type <= 31 && hdr + 2 < n)
            na[nnals].first_slice = (d[hdr + 2] & 0x80) != 0;
        nnals++;
    }
    if (!nnals) { free(na); return -1; }

    /* Group NALs into access units: a new AU starts at a VCL NAL whose
     * first_slice_segment_in_pic_flag is set (after at least one VCL). */
    size_t ocap = 256, ocnt = 0;
    size_t *o = malloc(ocap * sizeof(*o));
    size_t *l = malloc(ocap * sizeof(*l));
    if (!o || !l) { free(o); free(l); free(na); return -1; }

    size_t au_start = na[0].off;
    int have_vcl = 0;
    for (size_t k = 0; k < nnals; k++) {
        if (na[k].type <= 31 && na[k].first_slice && have_vcl) {
            if (ocnt == ocap) {
                ocap *= 2;
                size_t *no = realloc(o, ocap * sizeof(*o));
                size_t *nl = realloc(l, ocap * sizeof(*l));
                if (!no || !nl) { free(no ? no : o); free(nl ? nl : l); free(na); return -1; }
                o = no; l = nl;
            }
            o[ocnt] = au_start;
            l[ocnt] = na[k].off - au_start;
            ocnt++;
            au_start = na[k].off;
        }
        if (na[k].type <= 31) have_vcl = 1;
    }
    if (ocnt == ocap) {
        ocap++;
        size_t *no = realloc(o, ocap * sizeof(*o));
        size_t *nl = realloc(l, ocap * sizeof(*l));
        if (!no || !nl) { free(no ? no : o); free(nl ? nl : l); free(na); return -1; }
        o = no; l = nl;
    }
    o[ocnt] = au_start;
    l[ocnt] = n - au_start;
    ocnt++;

    free(na);
    *offs = o;
    *lens = l;
    *count = ocnt;
    return 0;
}

static void out_release(struct ctx *c, unsigned int idx) {
    if (c->n_out_free < MAX_OUT_BUFS) c->out_free[c->n_out_free++] = (int)idx;
}

static int out_alloc(struct ctx *c, unsigned int *idx) {
    if (c->n_out_free <= 0) return 0;
    *idx = (unsigned int)c->out_free[--c->n_out_free];
    return 1;
}

static void fed_push(struct ctx *c, uint32_t seq, uint64_t send_ns, uint64_t recv_ns) {
    if (c->fed_head - c->fed_tail >= MAX_FED) c->fed_tail++;
    struct fed_au *f = &c->fed[c->fed_head % MAX_FED];
    f->seq = seq;
    f->send_ns = send_ns;
    f->recv_ns = recv_ns;
    c->fed_head++;
}

static int fed_pop(struct ctx *c, struct fed_au *out) {
    if (c->fed_tail >= c->fed_head) return 0;
    *out = c->fed[c->fed_tail % MAX_FED];
    c->fed_tail++;
    return 1;
}

static int out_fill_data(struct ctx *c, unsigned int idx, const void *data, size_t n) {
    if (n > c->out[idx].len) {
        fprintf(stderr, "AU len %zu exceeds OUTPUT buffer %zu\n", n, c->out[idx].len);
        return -1;
    }
    memcpy(c->out[idx].addr, data, n);
    struct v4l2_buffer b;
    struct v4l2_plane planes[VIDEO_MAX_PLANES];
    memset(&b, 0, sizeof(b));
    memset(planes, 0, sizeof(planes));
    b.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
    b.memory = V4L2_MEMORY_MMAP;
    b.index = idx;
    b.length = 1;
    b.m.planes = planes;
    planes[0].bytesused = (uint32_t)n;
    if (xioctl(c->video_fd, VIDIOC_QBUF, &b) < 0) { perror("QBUF OUTPUT"); return -1; }
    return 1;
}

static int out_fill(struct ctx *c, unsigned int idx) {
    if (c->next_chunk >= c->n_chunks) return 0;
    size_t off = c->chunk_off[c->next_chunk];
    size_t n = c->chunk_len[c->next_chunk];
    int r = out_fill_data(c, idx, c->in_data + off, n);
    if (r < 0) return -1;
    c->next_chunk++;
    return 1;
}

static int v4l2_output_setup(struct ctx *c) {
    size_t maxlen = 0;
    for (size_t i = 0; i < c->n_chunks; i++)
        if (c->chunk_len[i] > maxlen) maxlen = c->chunk_len[i];
    if (!maxlen) return -1;
    maxlen = (maxlen + 4095) & ~(size_t)4095;

    struct v4l2_format f;
    memset(&f, 0, sizeof(f));
    f.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
    f.fmt.pix_mp.width = c->video_w;
    f.fmt.pix_mp.height = c->video_h;
    f.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_HEVC;
    f.fmt.pix_mp.field = V4L2_FIELD_NONE;
    f.fmt.pix_mp.num_planes = 1;
    f.fmt.pix_mp.plane_fmt[0].sizeimage = (uint32_t)maxlen;
    if (xioctl(c->video_fd, VIDIOC_S_FMT, &f) < 0) { perror("S_FMT OUTPUT"); return -1; }
    printf("OUTPUT S_FMT %ux%u sizeimage=%u (max NAL chunk %zu)\n",
           f.fmt.pix_mp.width, f.fmt.pix_mp.height,
           f.fmt.pix_mp.plane_fmt[0].sizeimage, maxlen);
    if (f.fmt.pix_mp.plane_fmt[0].sizeimage < maxlen) {
        fprintf(stderr, "driver shrank OUTPUT sizeimage to %u < %zu\n",
                f.fmt.pix_mp.plane_fmt[0].sizeimage, maxlen);
        return -1;
    }

    struct v4l2_requestbuffers rb;
    memset(&rb, 0, sizeof(rb));
    rb.count = c->n_chunks < 8 ? (unsigned int)c->n_chunks : 8;
    rb.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
    rb.memory = V4L2_MEMORY_MMAP;
    if (xioctl(c->video_fd, VIDIOC_REQBUFS, &rb) < 0) { perror("REQBUFS OUTPUT"); return -1; }
    c->num_out = rb.count;
    printf("OUTPUT REQBUFS count=%u, NAL chunks=%zu\n", c->num_out, c->n_chunks);

    for (unsigned int i = 0; i < c->num_out; i++) {
        struct v4l2_buffer b;
        struct v4l2_plane planes[VIDEO_MAX_PLANES];
        memset(&b, 0, sizeof(b));
        memset(planes, 0, sizeof(planes));
        b.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
        b.memory = V4L2_MEMORY_MMAP;
        b.index = i;
        b.length = 1;
        b.m.planes = planes;
        if (xioctl(c->video_fd, VIDIOC_QUERYBUF, &b) < 0) { perror("QUERYBUF OUTPUT"); return -1; }
        c->out[i].len = planes[0].length;
        c->out[i].addr = mmap(NULL, planes[0].length, PROT_READ | PROT_WRITE,
                              MAP_SHARED, c->video_fd, planes[0].m.mem_offset);
        if (c->out[i].addr == MAP_FAILED) { perror("mmap OUTPUT"); return -1; }
        int r = out_fill(c, i);
        if (r < 0) return -1;
        if (r == 0) break;
    }

    uint32_t type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
    if (xioctl(c->video_fd, VIDIOC_STREAMON, &type) < 0) { perror("STREAMON OUTPUT"); return -1; }
    return 0;
}

static int sock_connect(const char *path) {
    int fd = socket(AF_UNIX, SOCK_SEQPACKET, 0);
    if (fd < 0) { perror("socket"); return -1; }
    struct sockaddr_un sa;
    memset(&sa, 0, sizeof(sa));
    sa.sun_family = AF_UNIX;
    snprintf(sa.sun_path, sizeof(sa.sun_path), "%s", path);
    for (int i = 0; i < 300; i++) { /* up to 30 s: sender may still be parsing */
        if (connect(fd, (struct sockaddr *)&sa, sizeof(sa)) == 0) return fd;
        usleep(100000);
    }
    perror("connect(AU socket)");
    close(fd);
    return -1;
}

static int sock_recv_msg(int fd, struct au_hdr *h, unsigned char *buf, size_t cap,
                         int timeout_ms) {
    struct pollfd p = { .fd = fd, .events = POLLIN | POLLERR | POLLHUP };
    int pr = poll(&p, 1, timeout_ms);
    if (pr == 0) return -2;
    if (pr < 0) return -1;
    ssize_t n = recv(fd, buf, cap, 0);
    if (n <= 0) return -1;
    if ((size_t)n < sizeof(*h)) return -1;
    memcpy(h, buf, sizeof(*h));
    if (h->magic != AU_MAGIC) return -1;
    if (h->len != (uint32_t)((size_t)n - sizeof(*h))) return -1;
    return (int)h->len;
}

static int v4l2_output_setup_socket(struct ctx *c) {
    struct v4l2_format f;
    memset(&f, 0, sizeof(f));
    f.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
    f.fmt.pix_mp.width = 1920;
    f.fmt.pix_mp.height = 1080;
    f.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_HEVC;
    f.fmt.pix_mp.field = V4L2_FIELD_NONE;
    f.fmt.pix_mp.num_planes = 1;
    f.fmt.pix_mp.plane_fmt[0].sizeimage = AU_MAX_BYTES;
    if (xioctl(c->video_fd, VIDIOC_S_FMT, &f) < 0) { perror("S_FMT OUTPUT"); return -1; }
    if (f.fmt.pix_mp.plane_fmt[0].sizeimage < AU_MAX_BYTES) {
        fprintf(stderr, "driver shrank OUTPUT sizeimage to %u < %u\n",
                f.fmt.pix_mp.plane_fmt[0].sizeimage, AU_MAX_BYTES);
        return -1;
    }

    struct v4l2_requestbuffers rb;
    memset(&rb, 0, sizeof(rb));
    rb.count = MAX_OUT_BUFS;
    rb.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
    rb.memory = V4L2_MEMORY_MMAP;
    if (xioctl(c->video_fd, VIDIOC_REQBUFS, &rb) < 0) { perror("REQBUFS OUTPUT"); return -1; }
    c->num_out = rb.count;
    printf("OUTPUT REQBUFS count=%u sizeimage=%u (socket AU mode)\n",
           c->num_out, f.fmt.pix_mp.plane_fmt[0].sizeimage);

    for (unsigned int i = 0; i < c->num_out; i++) {
        struct v4l2_buffer b;
        struct v4l2_plane planes[VIDEO_MAX_PLANES];
        memset(&b, 0, sizeof(b));
        memset(planes, 0, sizeof(planes));
        b.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
        b.memory = V4L2_MEMORY_MMAP;
        b.index = i;
        b.length = 1;
        b.m.planes = planes;
        if (xioctl(c->video_fd, VIDIOC_QUERYBUF, &b) < 0) { perror("QUERYBUF OUTPUT"); return -1; }
        c->out[i].len = planes[0].length;
        c->out[i].addr = mmap(NULL, planes[0].length, PROT_READ | PROT_WRITE,
                              MAP_SHARED, c->video_fd, planes[0].m.mem_offset);
        if (c->out[i].addr == MAP_FAILED) { perror("mmap OUTPUT"); return -1; }
        out_release(c, i);
    }
    return 0;
}

static int v4l2_subscribe_source_change(struct ctx *c) {
    struct v4l2_event_subscription sub;
    memset(&sub, 0, sizeof(sub));
    sub.type = V4L2_EVENT_SOURCE_CHANGE;
    if (xioctl(c->video_fd, VIDIOC_SUBSCRIBE_EVENT, &sub) < 0) { perror("SUBSCRIBE_EVENT"); return -1; }
    return 0;
}

static int v4l2_wait_source_change(struct ctx *c, int timeout_ms) {
    double t0 = now_ms();
    double deadline = t0 + timeout_ms;
    while (!g_stop && now_ms() < deadline) {
        struct pollfd pfd = { .fd = c->video_fd, .events = POLLIN | POLLPRI | POLLERR };
        int pr = poll(&pfd, 1, 200);
        if (pr < 0) { if (errno == EINTR) continue; perror("poll"); return -1; }
        if (pr == 0) continue;
        if (pfd.revents & POLLERR) { fprintf(stderr, "POLLERR on video fd\n"); return -1; }
        for (;;) {
            struct v4l2_event ev;
            memset(&ev, 0, sizeof(ev));
            if (xioctl(c->video_fd, VIDIOC_DQEVENT, &ev) < 0) break;
            if (ev.type == V4L2_EVENT_SOURCE_CHANGE) {
                printf("SOURCE_CHANGE changes=0x%x after %.1f ms\n",
                       ev.u.src_change.changes, now_ms() - t0);
                return 0;
            }
        }
    }
    fprintf(stderr, "no SOURCE_CHANGE within %d ms\n", timeout_ms);
    return -1;
}

static int v4l2_capture_setup(struct ctx *c) {
    struct v4l2_format f;
    memset(&f, 0, sizeof(f));
    f.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
    if (xioctl(c->video_fd, VIDIOC_G_FMT, &f) < 0) { perror("G_FMT CAPTURE"); return -1; }
    c->video_w = f.fmt.pix_mp.width;
    c->video_h = f.fmt.pix_mp.height;
    for (unsigned int p = 0; p < 2; p++) {
        c->bpl[p] = f.fmt.pix_mp.plane_fmt[p].bytesperline;
        c->plane_size[p] = f.fmt.pix_mp.plane_fmt[p].sizeimage;
    }
    printf("CAPTURE G_FMT %ux%u %.4s planes=%u bpl=%u/%u size=%u/%u\n",
           c->video_w, c->video_h, (const char *)&f.fmt.pix_mp.pixelformat,
           f.fmt.pix_mp.num_planes, c->bpl[0], c->bpl[1],
           c->plane_size[0], c->plane_size[1]);
    if (f.fmt.pix_mp.pixelformat != V4L2_PIX_FMT_NV12M || f.fmt.pix_mp.num_planes != 2) {
        fprintf(stderr, "unexpected CAPTURE format\n");
        return -1;
    }
    if (c->card_fd >= 0 && (c->video_w > c->disp_w || c->video_h > c->disp_h)) {
        fprintf(stderr, "video %ux%u does not fit display %ux%u\n",
                c->video_w, c->video_h, c->disp_w, c->disp_h);
        return -1;
    }

    struct v4l2_control ctl;
    memset(&ctl, 0, sizeof(ctl));
    ctl.id = V4L2_CID_MIN_BUFFERS_FOR_CAPTURE;
    int dpb = 1;
    if (xioctl(c->video_fd, VIDIOC_G_CTRL, &ctl) == 0) dpb = ctl.value;
    printf("min_buffers_for_capture=%d\n", dpb);

    /* dpb_size alone is not enough: the driver also needs buffers for the
     * frame(s) being decoded, otherwise it aborts with "No dst buffer". */
    unsigned int want = (unsigned int)dpb + 4;
    if (want < 8) want = 8;
    if (c->cap_bufs > 0) want = (unsigned int)c->cap_bufs;
    if (want > MAX_CAP_BUFS) want = MAX_CAP_BUFS;

    struct v4l2_requestbuffers rb;
    memset(&rb, 0, sizeof(rb));
    rb.count = want;
    rb.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
    rb.memory = V4L2_MEMORY_MMAP;
    if (xioctl(c->video_fd, VIDIOC_REQBUFS, &rb) < 0) { perror("REQBUFS CAPTURE"); return -1; }
    c->num_cap = rb.count;
    printf("CAPTURE REQBUFS count=%u (wanted %u)\n", c->num_cap, want);
    if (c->num_cap < want) {
        fprintf(stderr,
                "driver allocated only %u of %u buffers (CMA fragmentation?); "
                "min_queued_buffers is still %u so STREAMON would fail\n",
                c->num_cap, want, want);
        return -1;
    }
    if (c->num_cap < 2) { fprintf(stderr, "need >=2 capture buffers\n"); return -1; }

    for (unsigned int i = 0; i < c->num_cap; i++) {
        struct v4l2_buffer b;
        struct v4l2_plane planes[VIDEO_MAX_PLANES];
        memset(&b, 0, sizeof(b));
        memset(planes, 0, sizeof(planes));
        b.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
        b.memory = V4L2_MEMORY_MMAP;
        b.index = i;
        b.length = 2;
        b.m.planes = planes;
        if (xioctl(c->video_fd, VIDIOC_QUERYBUF, &b) < 0) { perror("QUERYBUF CAPTURE"); return -1; }
        for (unsigned int p = 0; p < 2; p++) {
            c->cap[i].maplen[p] = planes[p].length;
            if (c->dump_dir || c->dump_recover_dir || c->dump_first_dir) {
                c->cap[i].map[p] = mmap(NULL, planes[p].length, PROT_READ, MAP_SHARED,
                                        c->video_fd, planes[p].m.mem_offset);
                if (c->cap[i].map[p] == MAP_FAILED) { perror("mmap CAPTURE"); c->cap[i].map[p] = NULL; return -1; }
            }
            if (c->card_fd < 0) continue; /* decode-only: no dmabuf export */

            struct v4l2_exportbuffer e;
            memset(&e, 0, sizeof(e));
            e.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
            e.index = i;
            e.plane = p;
            e.flags = O_CLOEXEC;
            if (xioctl(c->video_fd, VIDIOC_EXPBUF, &e) < 0) { perror("EXPBUF"); return -1; }
            c->cap[i].dmabuf[p] = e.fd;

            struct drm_prime_handle ph;
            memset(&ph, 0, sizeof(ph));
            ph.fd = e.fd;
            ph.flags = DRM_CLOEXEC;
            if (xioctl(c->card_fd, DRM_IOCTL_PRIME_FD_TO_HANDLE, &ph) < 0) { perror("PRIME_FD_TO_HANDLE"); return -1; }
            c->cap[i].handle[p] = ph.handle;
        }
        if (c->card_fd < 0) { c->cap[i].fb_id = 0; }
        else {
        struct drm_mode_fb_cmd2 fb;
        memset(&fb, 0, sizeof(fb));
        fb.width = c->video_w;
        fb.height = c->video_h;
        fb.pixel_format = FOURCC('N', 'V', '1', '2');
        fb.handles[0] = c->cap[i].handle[0];
        fb.handles[1] = c->cap[i].handle[1];
        fb.pitches[0] = c->bpl[0];
        fb.pitches[1] = c->bpl[1];
        fb.offsets[0] = 0;
        fb.offsets[1] = 0;
        if (xioctl(c->card_fd, DRM_IOCTL_MODE_ADDFB2, &fb) < 0) { perror("ADDFB2"); return -1; }
        c->cap[i].fb_id = fb.fb_id;
        printf("cap[%u] dmabuf=%d/%d gem=%u/%u fb=%u\n", i,
               c->cap[i].dmabuf[0], c->cap[i].dmabuf[1],
               c->cap[i].handle[0], c->cap[i].handle[1], c->cap[i].fb_id);
        }

        memset(&b, 0, sizeof(b));
        memset(planes, 0, sizeof(planes));
        b.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
        b.memory = V4L2_MEMORY_MMAP;
        b.index = i;
        b.length = 2;
        b.m.planes = planes;
        if (xioctl(c->video_fd, VIDIOC_QBUF, &b) < 0) { perror("QBUF CAPTURE"); return -1; }
        c->cap[i].queued = 1;
    }

    uint32_t type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
    if (xioctl(c->video_fd, VIDIOC_STREAMON, &type) < 0) { perror("STREAMON CAPTURE"); return -1; }
    return 0;
}

static int dump_planes(const char *path, const uint8_t *y, const uint8_t *uv,
                       uint32_t w, uint32_t h, uint32_t bpl0, uint32_t bpl1) {
    FILE *fp = fopen(path, "wb");
    if (!fp) { perror(path); return -1; }
    for (uint32_t r = 0; r < h; r++)
        fwrite(y + (size_t)r * bpl0, 1, w, fp);
    for (uint32_t r = 0; r < h / 2; r++)
        fwrite(uv + (size_t)r * bpl1, 1, w, fp);
    fclose(fp);
    printf("dumped %s\n", path);
    return 0;
}

static int dump_frame(struct ctx *c, unsigned int idx, unsigned int seq) {
    if (!c->dump_dir || (int)seq >= c->dump_frames) return 0;
    char path[512];
    snprintf(path, sizeof(path), "%s/frame_%04u_%ux%u.yuv", c->dump_dir, seq,
             c->video_w, c->video_h);
    return dump_planes(path, c->cap[idx].map[0], c->cap[idx].map[1],
                       c->video_w, c->video_h, c->bpl[0], c->bpl[1]);
}

/* First frames after a rebuild (and the last held frame) for flash analysis. */
static int dump_first_frame(struct ctx *c, unsigned int idx) {
    if (!c->dump_first_dir || c->first_dumps >= c->first_dump_max) return 0;
    if (!c->cap[idx].map[0] || !c->cap[idx].map[1]) return 0;
    char path[512];
    snprintf(path, sizeof(path), "%s/first_%04d_%ux%u.yuv", c->dump_first_dir,
             c->first_dumps, c->video_w, c->video_h);
    c->first_dumps++;
    return dump_planes(path, c->cap[idx].map[0], c->cap[idx].map[1],
                       c->video_w, c->video_h, c->bpl[0], c->bpl[1]);
}

static int dump_recover_frame(struct ctx *c, unsigned int idx) {
    if (!c->dump_recover_dir || !c->rec_active || c->rec_dumps >= c->rec_dump_max)
        return 0;
    if (!c->cap[idx].map[0] || !c->cap[idx].map[1]) return 0;
    char path[512];
    snprintf(path, sizeof(path), "%s/rec_%.1f_%d_%ux%u.yuv", c->dump_recover_dir,
             now_ms(), c->rec_dumps, c->video_w, c->video_h);
    c->rec_dumps++;
    if (c->rec_dumps >= c->rec_dump_max) c->rec_active = 0;
    return dump_planes(path, c->cap[idx].map[0], c->cap[idx].map[1],
                       c->video_w, c->video_h, c->bpl[0], c->bpl[1]);
}

static int cap_requeue(struct ctx *c, unsigned int idx) {
    struct v4l2_buffer q;
    struct v4l2_plane qp[VIDEO_MAX_PLANES];
    memset(&q, 0, sizeof(q));
    memset(qp, 0, sizeof(qp));
    q.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
    q.memory = V4L2_MEMORY_MMAP;
    q.index = idx;
    q.length = 2;
    q.m.planes = qp;
    if (xioctl(c->video_fd, VIDIOC_QBUF, &q) < 0) { perror("QBUF CAPTURE"); return -1; }
    c->cap[idx].queued = 1;
    return 0;
}

static int run_decode(struct ctx *c, int max_frames, int no_display) {
    int frames = 0, corrupt = 0;
    double t0 = now_ms();
    double last_log = t0;
    double last_progress = t0;
    while (!g_stop && (max_frames <= 0 || frames < max_frames)) {
        struct pollfd pfd = { .fd = c->video_fd, .events = POLLIN | POLLPRI | POLLERR };
        int pr = poll(&pfd, 1, 500);
        if (pr < 0) { if (errno == EINTR) continue; perror("poll"); return -1; }
        if (pfd.revents & POLLERR) { fprintf(stderr, "POLLERR while decoding\n"); return -1; }

        /* Recycle OUTPUT as soon as the parser releases it. Feeding the whole
         * file up front lets the decoder outrun userspace and exhaust the DPB. */
        for (;;) {
            struct v4l2_buffer ob;
            struct v4l2_plane op[VIDEO_MAX_PLANES];
            memset(&ob, 0, sizeof(ob));
            memset(op, 0, sizeof(op));
            ob.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
            ob.memory = V4L2_MEMORY_MMAP;
            ob.length = 1;
            ob.m.planes = op;
            if (xioctl(c->video_fd, VIDIOC_DQBUF, &ob) < 0) {
                if (errno == EAGAIN) break;
                perror("DQBUF OUTPUT");
                return -1;
            }
            if (out_fill(c, ob.index) < 0) return -1;
        }

        if (pr == 0) {
            if (now_ms() - last_progress > 20000) {
                fprintf(stderr, "no capture frame for 20 s (fed %zu/%zu chunks)\n",
                        c->next_chunk, c->n_chunks);
                return -1;
            }
            continue;
        }

        struct v4l2_buffer b;
        struct v4l2_plane planes[VIDEO_MAX_PLANES];
        memset(&b, 0, sizeof(b));
        memset(planes, 0, sizeof(planes));
        b.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
        b.memory = V4L2_MEMORY_MMAP;
        b.length = 2;
        b.m.planes = planes;
        if (xioctl(c->video_fd, VIDIOC_DQBUF, &b) < 0) {
            if (errno == EAGAIN) continue;
            perror("DQBUF CAPTURE");
            return -1;
        }
        unsigned int idx = b.index;
        c->cap[idx].queued = 0;
        if (b.flags & V4L2_BUF_FLAG_ERROR) {
            corrupt++;
            fprintf(stderr, "capture buffer flagged ERROR (idx=%u corrupt=%d)\n", idx, corrupt);
            if (cap_requeue(c, idx) < 0) return -1;
            continue;
        }
        if (dump_frame(c, idx, (unsigned int)frames) < 0) return -1;

        if (!no_display) {
            if (drm_present(c, (int)idx) < 0) return -1;
            /* Blocking SETPLANE returned after the previous flip completed. */
            if (c->last_idx >= 0 && !c->cap[c->last_idx].queued) {
                if (cap_requeue(c, (unsigned int)c->last_idx) < 0) return -1;
            }
            c->last_idx = (int)idx;
            c->last_fb = c->cap[idx].fb_id;
        } else {
            if (cap_requeue(c, idx) < 0) return -1;
        }
        frames++;
        last_progress = now_ms();
        double now = last_progress;
        if (now - last_log > 1000) {
            printf("frames=%d corrupt=%d %.1f fps\n", frames, corrupt,
                   frames * 1000.0 / (now - t0));
            last_log = now;
        }
    }
    double dt = (now_ms() - t0) / 1000.0;
    printf("DECODED frames=%d corrupt=%d wall=%.3fs fps=%.2f\n",
           frames, corrupt, dt, dt > 0 ? frames / dt : 0);
    return frames > 0 ? 0 : -1;
}

static uint32_t plane_fb_id(struct ctx *c, uint32_t plane_id) {
    if (c->card_fd < 0 || !plane_id) return 0xffffffffu;
    struct drm_mode_get_plane p;
    memset(&p, 0, sizeof(p));
    p.plane_id = plane_id;
    if (xioctl(c->card_fd, DRM_IOCTL_MODE_GETPLANE, &p) < 0) return 0xffffffffu;
    return p.fb_id;
}

static void mark_recovering(struct ctx *c, const char *why) {
    if (c->recovering) return;
    c->recovering = 1;
    c->recover_start_ms = now_ms();
    c->have_recover_last_present = c->have_last_present;
    c->recover_last_present_ms = c->last_present_ms;
    c->rec_dumps = 0;
    c->rec_active = 1;
    c->held_dumped = 0;
    if (!c->gate_open) c->gate_frames = 0;
    fprintf(stderr, "RECOVER begin t=%.1f (%s) since_last_present_ms=%.1f primary_fb=%u\n",
            c->recover_start_ms, why,
            c->have_last_present ? c->recover_start_ms - c->last_present_ms : -1.0,
            plane_fb_id(c, c->primary_id));
    if (c->sock_fd >= 0) {
        ssize_t n = send(c->sock_fd, "R", 1, MSG_DONTWAIT);
        (void)n;
    }
}

static int cap_present_one(struct ctx *c, int no_display, int *frames, int *corrupt,
                           int backlog, int session) {
    (void)backlog;
    struct v4l2_buffer b;
    struct v4l2_plane planes[VIDEO_MAX_PLANES];
    memset(&b, 0, sizeof(b));
    memset(planes, 0, sizeof(planes));
    b.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
    b.memory = V4L2_MEMORY_MMAP;
    b.length = 2;
    b.m.planes = planes;
    if (xioctl(c->video_fd, VIDIOC_DQBUF, &b) < 0) {
        if (errno == EAGAIN) return 0;
        perror("DQBUF CAPTURE");
        mark_recovering(c, "DQBUF EIO");
        return -1;
    }
    uint64_t dq_ns = mono_ns();
    unsigned int idx = b.index;
    c->cap[idx].queued = 0;
    if (b.flags & V4L2_BUF_FLAG_ERROR) {
        (*corrupt)++;
        fprintf(stderr, "capture buffer flagged ERROR (idx=%u corrupt=%d)\n", idx, *corrupt);
        if (cap_requeue(c, idx) < 0) { mark_recovering(c, "QBUF CAPTURE"); return -1; }
        return 1;
    }

    /* L2-B: drain all ready frames and present only the newest.  Older decoded
     * frames are requeued without display; the decoder still decoded them, so
     * the reference chain is untouched. */
    int skipped = 0;
    struct fed_au fed = {0};
    int have_fed = fed_pop(c, &fed);
    if (!no_display) {
        for (;;) {
            struct v4l2_buffer nb;
            struct v4l2_plane np[VIDEO_MAX_PLANES];
            memset(&nb, 0, sizeof(nb));
            memset(np, 0, sizeof(np));
            nb.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
            nb.memory = V4L2_MEMORY_MMAP;
            nb.length = 2;
            nb.m.planes = np;
            if (xioctl(c->video_fd, VIDIOC_DQBUF, &nb) < 0) {
                if (errno == EAGAIN) break;
                perror("DQBUF CAPTURE");
                mark_recovering(c, "DQBUF EIO");
                return -1;
            }
            unsigned int nidx = nb.index;
            c->cap[nidx].queued = 0;
            if (nb.flags & V4L2_BUF_FLAG_ERROR) {
                (*corrupt)++;
                fprintf(stderr, "capture buffer flagged ERROR (idx=%u corrupt=%d)\n",
                        nidx, *corrupt);
                if (cap_requeue(c, nidx) < 0) { mark_recovering(c, "QBUF CAPTURE"); return -1; }
                continue;
            }
            if (cap_requeue(c, idx) < 0) { mark_recovering(c, "QBUF CAPTURE"); return -1; }
            skipped++;
            idx = nidx;
            dq_ns = mono_ns();
            struct fed_au nf;
            if (fed_pop(c, &nf)) { fed = nf; have_fed = 1; } else { have_fed = 0; }
        }
    }

    if (c->dump_dir && dump_frame(c, idx, (unsigned int)*frames) < 0) return -1;
    if (dump_first_frame(c, idx) < 0) return -1;
    if (dump_recover_frame(c, idx) < 0) return -1;
    /* Startup gate: keep the console until the stream has survived N decoded
     * frames without a rebuild; the first 0xf usually happens within ~1 s. */
    if (!no_display && !c->gate_open && c->start_gate > 0) {
        c->gate_frames += 1 + skipped;
        if (c->gate_frames < c->start_gate) {
            c->gated_frames += 1 + skipped;
            if (cap_requeue(c, idx) < 0) { mark_recovering(c, "QBUF CAPTURE"); return -1; }
            return 1;
        }
        c->gate_open = 1;
        printf("START_GATE open after %d frames t=%.1f\n", c->gate_frames, now_ms());
    }
    if (!no_display) {
        if (drm_present(c, (int)idx) < 0) return -1;
    }
    uint64_t done_ns = mono_ns();
    if (!no_display) {
        /* Return the buffer from two presents ago: the meson flip can still be
         * scanning the previous one, and requeueing it lets the decoder write
         * over a frame that is on screen (partial black/tearing). */
        if (c->prev_idx >= 0 && !c->cap[c->prev_idx].queued) {
            if (cap_requeue(c, (unsigned int)c->prev_idx) < 0) {
                mark_recovering(c, "QBUF CAPTURE");
                return -1;
            }
        }
        c->prev_idx = c->last_idx;
        c->last_idx = (int)idx;
        c->last_fb = c->cap[idx].fb_id;
        c->have_last_present = 1;
        c->last_present_ms = (double)done_ns / 1e6;
    } else {
        if (cap_requeue(c, idx) < 0) { mark_recovering(c, "QBUF CAPTURE"); return -1; }
    }
    double age_ms = -1.0, decode_ms = -1.0, wait_ms = -1.0;
    if (have_fed) {
        if (c->have_pop_seq && fed.seq != c->last_pop_seq + 1) c->seq_gaps++;
        c->last_pop_seq = fed.seq;
        c->have_pop_seq = 1;
        age_ms = (done_ns - fed.send_ns) / 1e6;
        decode_ms = (dq_ns - fed.recv_ns) / 1e6;
        wait_ms = (done_ns - dq_ns) / 1e6;
        if (c->age_n < MAX_AGE_SAMPLES) c->age_ms[c->age_n++] = age_ms;
        if (c->lat_fp) {
            fprintf(c->lat_fp, "%d,%u,%llu,%.2f,%.2f,%.2f,%d,%d\n",
                    *frames, fed.seq, (unsigned long long)done_ns,
                    age_ms, decode_ms, wait_ms, skipped, session);
        }
    }
    if (skipped > c->backlog_max) c->backlog_max = skipped;
    (*frames)++;
    if (c->recovering) {
        printf("RECOVER first_frame t=%.1f dt=%.1f", now_ms(), now_ms() - c->recover_start_ms);
        if (c->have_recover_last_present) {
            printf(" VISIBLE_GAP gap_ms=%.1f", (double)done_ns / 1e6 - c->recover_last_present_ms);
        }
        printf(" primary_fb=%u\n", plane_fb_id(c, c->primary_id));
        c->recovering = 0;
    }
    return 1;
}

static int session_open(struct ctx *c) {
    if (c->video_fd < 0) {
        c->video_fd = open("/dev/video0", O_RDWR | O_NONBLOCK);
        if (c->video_fd < 0) { perror("open /dev/video0"); return -1; }
        if (v4l2_subscribe_source_change(c) < 0) return -1;
    }
    if (v4l2_output_setup_socket(c) < 0) {
        /* A reused fd can become unusable after an abort: rebuild from scratch. */
        fprintf(stderr, "reused fd config failed; reopening device\n");
        if (c->video_fd >= 0) { close(c->video_fd); c->video_fd = -1; }
        c->video_fd = open("/dev/video0", O_RDWR | O_NONBLOCK);
        if (c->video_fd < 0) { perror("open /dev/video0 (retry)"); return -1; }
        if (v4l2_subscribe_source_change(c) < 0) return -1;
        if (v4l2_output_setup_socket(c) < 0) return -1;
    }
    return 0;
}

static void held_release(struct ctx *c) {
    for (int h = 0; h < c->held_n; h++) {
        struct held_fb *hf = &c->held[h];
        if (!hf->active) continue;
        for (unsigned int p = 0; p < 2; p++) {
            if (hf->map[p]) { munmap(hf->map[p], hf->maplen[p]); hf->map[p] = NULL; }
            if (hf->dmabuf[p] >= 0) { close(hf->dmabuf[p]); hf->dmabuf[p] = -1; }
        }
        if (c->card_fd >= 0 && hf->handle[0]) {
            struct drm_gem_close gc = { .handle = hf->handle[0] };
            xioctl(c->card_fd, DRM_IOCTL_GEM_CLOSE, &gc);
            hf->handle[0] = 0;
        }
        if (c->card_fd >= 0 && hf->handle[1]) {
            struct drm_gem_close gc = { .handle = hf->handle[1] };
            xioctl(c->card_fd, DRM_IOCTL_GEM_CLOSE, &gc);
            hf->handle[1] = 0;
        }
        if (c->card_fd >= 0 && hf->fb_id) {
            uint32_t fb = hf->fb_id;
            xioctl(c->card_fd, DRM_IOCTL_MODE_RMFB, &fb);
            hf->fb_id = 0;
        }
        hf->active = 0;
    }
    c->held_n = 0;
    c->held_release_countdown = 0;
}

/* Keep one more recent frame: the meson flip can take effect late, so the
 * plane may still scan the previous frame when it is freed. */
static int held_add(struct ctx *c, unsigned int i) {
    if (c->held_n >= 2 || !c->cap[i].fb_id) return 0;
    struct held_fb *hf = &c->held[c->held_n++];
    hf->active = 1;
    hf->fb_id = c->cap[i].fb_id;
    for (unsigned int p = 0; p < 2; p++) {
        hf->dmabuf[p] = c->cap[i].dmabuf[p];
        hf->handle[p] = c->cap[i].handle[p];
        hf->map[p] = c->cap[i].map[p];
        hf->maplen[p] = c->cap[i].maplen[p];
        c->cap[i].dmabuf[p] = -1;
        c->cap[i].handle[p] = 0;
        c->cap[i].map[p] = NULL;
    }
    c->cap[i].fb_id = 0;
    return 1;
}

static void session_teardown(struct ctx *c, int keep_fd) {
    /* If a newer frame was presented after the held frame (countdown > 0),
     * the held one is no longer scanned and can be freed before we keep the
     * current scanout.  countdown == 0 means no frame was presented yet. */
    if (c->held_n > 0 && c->held_release_countdown > 0) {
        held_release(c);
    }
    /* AUs fed in the dead session will never produce a frame; drop their
     * latency entries so the next session starts with a clean FIFO. */
    c->fed_head = c->fed_tail = 0;
    c->age_n = 0;
    c->backlog_max = 0;
    c->have_pop_seq = 0;
    if (!c->gate_open) c->gate_frames = 0;
    if (c->video_fd >= 0) {
        uint32_t type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
        xioctl(c->video_fd, VIDIOC_STREAMOFF, &type);
        type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
        xioctl(c->video_fd, VIDIOC_STREAMOFF, &type);
    }
    for (unsigned int i = 0; i < c->num_cap; i++) {
        /* Keep the frame that is currently on screen alive so the overlay
         * keeps scanning it during the V4L2 rebuild (no black flash). */
        if (((int)i == c->last_idx || (int)i == c->prev_idx) && held_add(c, i))
            continue;
        for (unsigned int p = 0; p < 2; p++) {
            if (c->cap[i].map[p]) { munmap(c->cap[i].map[p], c->cap[i].maplen[p]); c->cap[i].map[p] = NULL; }
            if (c->cap[i].dmabuf[p] >= 0) { close(c->cap[i].dmabuf[p]); c->cap[i].dmabuf[p] = -1; }
        }
        if (c->card_fd >= 0 && c->cap[i].handle[0]) {
            struct drm_gem_close gc = { .handle = c->cap[i].handle[0] };
            xioctl(c->card_fd, DRM_IOCTL_GEM_CLOSE, &gc);
            c->cap[i].handle[0] = 0;
        }
        if (c->card_fd >= 0 && c->cap[i].handle[1]) {
            struct drm_gem_close gc = { .handle = c->cap[i].handle[1] };
            xioctl(c->card_fd, DRM_IOCTL_GEM_CLOSE, &gc);
            c->cap[i].handle[1] = 0;
        }
        if (c->card_fd >= 0 && c->cap[i].fb_id) {
            uint32_t fb = c->cap[i].fb_id;
            xioctl(c->card_fd, DRM_IOCTL_MODE_RMFB, &fb);
            c->cap[i].fb_id = 0;
        }
    }
    if (c->video_fd >= 0 && c->num_cap) {
        struct v4l2_requestbuffers rb;
        memset(&rb, 0, sizeof(rb));
        rb.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
        rb.memory = V4L2_MEMORY_MMAP;
        xioctl(c->video_fd, VIDIOC_REQBUFS, &rb);
    }
    if (c->video_fd >= 0 && c->num_out) {
        struct v4l2_requestbuffers rb;
        memset(&rb, 0, sizeof(rb));
        rb.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
        rb.memory = V4L2_MEMORY_MMAP;
        xioctl(c->video_fd, VIDIOC_REQBUFS, &rb);
    }
    for (unsigned int i = 0; i < c->num_out; i++) {
        if (c->out[i].addr) { munmap(c->out[i].addr, c->out[i].len); c->out[i].addr = NULL; }
    }
    c->num_cap = 0;
    c->num_out = 0;
    c->n_out_free = 0;
    c->last_idx = -1;
    c->last_fb = 0;
    if (!keep_fd && c->video_fd >= 0) {
        close(c->video_fd);
        c->video_fd = -1;
    }
}

static void session_close(struct ctx *c) {
    session_teardown(c, 0);
}

/* Wait until an IRAP AU arrives; non-IRAP AUs are dropped while recovering. */
static int wait_irap_au(struct ctx *c, struct au_hdr *h, unsigned char *msg, int timeout_ms) {
    double deadline = now_ms() + timeout_ms;
    while (!g_stop && now_ms() < deadline) {
        int n = sock_recv_msg(c->sock_fd, h, msg, sizeof(*h) + AU_MAX_BYTES, 500);
        if (n == -2) continue;
        if (n < 0) return -1;
        if (h->flags & AU_FLAG_EOS) return 0;
        if (h->flags & AU_FLAG_IRAP) return n;
    }
    return -1;
}

static int cmp_double_(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

static void report_second(struct ctx *c, int frames, int corrupt, int oversize,
                          int eos, int sessions, double now, double t0) {
    double p50 = -1, p95 = -1, mx = -1;
    if (c->age_n > 0) {
        qsort(c->age_ms, (size_t)c->age_n, sizeof(double), cmp_double_);
        p50 = c->age_ms[c->age_n / 2];
        int idx95 = (int)(c->age_n * 0.95);
        if (idx95 >= c->age_n) idx95 = c->age_n - 1;
        p95 = c->age_ms[idx95];
        mx = c->age_ms[c->age_n - 1];
    }
    printf("aus_frames=%d corrupt=%d oversize=%d eos=%d sessions=%d %.1f fps "
           "age_p50=%.1f age_p95=%.1f age_max=%.1f backlog_max=%d\n",
           frames, corrupt, oversize, eos, sessions, frames * 1000.0 / (now - t0),
           p50, p95, mx, c->backlog_max);
    c->age_n = 0;
    c->backlog_max = 0;
}

static int run_socket(struct ctx *c, int frames_limit) {
    unsigned char *msg = malloc(sizeof(struct au_hdr) + AU_MAX_BYTES);
    if (!msg) return -1;
    struct au_hdr h;
    int frames = 0, corrupt = 0, oversize = 0, eos = 0, sessions = 0;
    double t0 = now_ms(), last_log = t0;

    while (!g_stop && (frames_limit <= 0 || frames < frames_limit)) {
        if (session_open(c) < 0) { session_close(c); break; }
        sessions++;
        printf("t=%.1f session %d opened; waiting for IRAP AU\n", now_ms(), sessions);
        if (c->recovering)
            printf("RECOVER reopened t=%.1f dt=%.1f\n", now_ms(), now_ms() - c->recover_start_ms);

        int n = wait_irap_au(c, &h, msg, 120000);
        if (n < 0) { fprintf(stderr, "socket closed while waiting for IRAP\n"); session_close(c); break; }
        if (n == 0) { eos = 1; session_close(c); break; }
        unsigned int idx;
        if (!out_alloc(c, &idx)) { session_close(c); break; }
        uint64_t recv_ns = mono_ns();
        if (out_fill_data(c, idx, msg + sizeof(h), (size_t)n) < 0) { session_close(c); break; }
        fed_push(c, h.seq, h.ts_ns, recv_ns);
        printf("t=%.1f first AU seq=%u len=%d flags=0x%x\n", now_ms(), h.seq, n, h.flags);

        uint32_t type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
        if (xioctl(c->video_fd, VIDIOC_STREAMON, &type) < 0) {
            perror("STREAMON OUTPUT");
            mark_recovering(c, "STREAMON");
            session_teardown(c, 0);
            continue;
        }
        if (v4l2_wait_source_change(c, 10000) < 0) {
            mark_recovering(c, "SOURCE_CHANGE timeout");
            session_teardown(c, 0); continue;
        }
        if (c->recovering)
            printf("RECOVER streamon t=%.1f dt=%.1f\n", now_ms(), now_ms() - c->recover_start_ms);
        if (v4l2_capture_setup(c) < 0) {
            mark_recovering(c, "capture setup");
            session_teardown(c, 0); continue;
        }
        if (c->recovering)
            printf("RECOVER capture_ready t=%.1f dt=%.1f\n", now_ms(), now_ms() - c->recover_start_ms);

        int recovered = 0;
        int backlog = 0;
        while (!g_stop && (frames_limit <= 0 || frames < frames_limit)) {
            struct pollfd pfds[2] = {
                { .fd = c->video_fd, .events = POLLIN | POLLPRI | POLLERR },
                { .fd = c->sock_fd, .events = POLLIN },
            };
            int pr = poll(pfds, 2, 500);
            if (pr < 0) { if (errno == EINTR) continue; perror("poll"); recovered = 1; break; }
            if (pfds[0].revents & POLLERR) {
                mark_recovering(c, "POLLERR");
                recovered = 1;
                break;
            }

            for (;;) {
                struct v4l2_buffer ob;
                struct v4l2_plane op[VIDEO_MAX_PLANES];
                memset(&ob, 0, sizeof(ob));
                memset(op, 0, sizeof(op));
                ob.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
                ob.memory = V4L2_MEMORY_MMAP;
                ob.length = 1;
                ob.m.planes = op;
                if (xioctl(c->video_fd, VIDIOC_DQBUF, &ob) < 0) {
                    if (errno == EAGAIN) break;
                    perror("DQBUF OUTPUT");
                    mark_recovering(c, "DQBUF OUTPUT");
                    recovered = 1;
                    break;
                }
                out_release(c, ob.index);
            }
            if (recovered) break;

            backlog = 0; /* frames already drained in this pass */
            for (;;) {
                int r = cap_present_one(c, c->card_fd < 0, &frames, &corrupt, backlog, sessions);
                if (r < 0) { recovered = 1; break; }
                if (r == 0) break;
                backlog++;
            }
            if (recovered) break;

            if (!(pfds[1].revents & (POLLIN | POLLHUP | POLLERR))) continue;
            int m = sock_recv_msg(c->sock_fd, &h, msg, sizeof(struct au_hdr) + AU_MAX_BYTES, 0);
            if (m == -2) continue;
            if (m < 0 || (h.flags & AU_FLAG_EOS)) { eos = 1; break; }
            if ((size_t)m > AU_MAX_BYTES) { oversize++; continue; }
            recv_ns = mono_ns();
            unsigned int oi;
            if (out_alloc(c, &oi)) {
                if (out_fill_data(c, oi, msg + sizeof(h), (size_t)m) < 0) { recovered = 1; break; }
                fed_push(c, h.seq, h.ts_ns, recv_ns);
            }

            double now = now_ms();
            if (now - last_log > 1000) {
                report_second(c, frames, corrupt, oversize, eos, sessions, now, t0);
                last_log = now;
            }
        }

        session_teardown(c, recovered ? 1 : 0);
        if (eos) break;
        if (recovered) {
            fprintf(stderr, "t=%.1f session %d rebuilt after error; frames=%d\n",
                    now_ms(), sessions, frames);
            if (c->recover_sleep_ms > 0)
                usleep((useconds_t)c->recover_sleep_ms * 1000);
            continue;
        }
        if (frames_limit > 0 && frames >= frames_limit) break;
    }

    double dt = (now_ms() - t0) / 1000.0;
    printf("DECODED frames=%d corrupt=%d oversize=%d sessions=%d seq_gaps=%u gated=%u "
           "wall=%.3fs fps=%.2f\n",
           frames, corrupt, oversize, sessions, c->seq_gaps, c->gated_frames,
           dt, dt > 0 ? frames / dt : 0.0);
    free(msg);
    return frames > 0 ? 0 : -1;
}

/* ---------------- teardown ---------------- */

static void cleanup(struct ctx *c) {
    if (c->card_fd >= 0 && c->master) {
        struct drm_mode_set_plane sp;
        memset(&sp, 0, sizeof(sp));
        sp.plane_id = c->plane_id;
        sp.crtc_id = c->crtc_id;
        sp.fb_id = 0;
        xioctl(c->card_fd, DRM_IOCTL_MODE_SETPLANE, &sp);
    }
    held_release(c);
    session_close(c);
    if (c->card_fd >= 0 && c->master && c->mode_changed && c->orig_mode_valid) {
        struct drm_mode_crtc sc;
        memset(&sc, 0, sizeof(sc));
        sc.crtc_id = c->crtc_id;
        sc.fb_id = c->orig_fb;
        sc.set_connectors_ptr = (uint64_t)(uintptr_t)&c->conn_id;
        sc.count_connectors = 1;
        sc.mode = c->orig_mode;
        sc.mode_valid = 1;
        if (xioctl(c->card_fd, DRM_IOCTL_MODE_SETCRTC, &sc) < 0)
            perror("SETCRTC(restore)");
        else
            printf("mode restored: %ux%u\n", c->orig_mode.hdisplay, c->orig_mode.vdisplay);
    }
    if (c->card_fd >= 0 && c->master) xioctl(c->card_fd, DRM_IOCTL_DROP_MASTER, 0);
    if (c->sock_fd >= 0) close(c->sock_fd);
    if (c->card_fd >= 0) close(c->card_fd);
    if (c->lat_fp) { fclose(c->lat_fp); c->lat_fp = NULL; }
}

static void usage(const char *argv0) {
    fprintf(stderr,
            "usage: %s --inventory\n"
            "       %s --file PATH [--bytes N] [--frames N] [--hold S] [--dump DIR]\n"
            "          [--dump-frames N] [--no-display] [--hide-primary] [--video WxH]\n"
            "          [--cap-bufs N]\n"
            "       %s --socket PATH [--frames N] [--hide-primary] [--cap-bufs N] [--mode WxH@Hz]\n"
            "          [--lat-csv PATH] [--dump-recover DIR] [--dump-first DIR] [--start-gate N]\n"
            "          [--recv-buf-kb N]\n",
            argv0, argv0, argv0);
}

int main(int argc, char **argv) {
    struct ctx c;
    setvbuf(stdout, NULL, _IONBF, 0);
    ctx_init(&c);
    const char *file = NULL, *sock_path = NULL;
    size_t limit = 0, filelen = 0;
    unsigned char *data = NULL;
    int inv = 0, no_display = 0, hide_primary = 0, frames = 1, hold_ms = 0, frames_set = 0;
    const char *lat_csv = NULL;
    c.dump_frames = 1;
    c.start_gate = 60;
    c.recover_sleep_ms = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--inventory")) inv = 1;
        else if (!strcmp(argv[i], "--no-display")) no_display = 1;
        else if (!strcmp(argv[i], "--hide-primary")) hide_primary = 1;
        else if (!strcmp(argv[i], "--file") && i + 1 < argc) file = argv[++i];
        else if (!strcmp(argv[i], "--socket") && i + 1 < argc) sock_path = argv[++i];
        else if (!strcmp(argv[i], "--lat-csv") && i + 1 < argc) lat_csv = argv[++i];
        else if (!strcmp(argv[i], "--bytes") && i + 1 < argc) limit = strtoull(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "--frames") && i + 1 < argc) { frames = atoi(argv[++i]); frames_set = 1; }
        else if (!strcmp(argv[i], "--hold") && i + 1 < argc) hold_ms = atoi(argv[++i]) * 1000;
        else if (!strcmp(argv[i], "--cap-bufs") && i + 1 < argc) c.cap_bufs = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--dump") && i + 1 < argc) c.dump_dir = argv[++i];
        else if (!strcmp(argv[i], "--dump-frames") && i + 1 < argc) c.dump_frames = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--dump-recover") && i + 1 < argc) {
            c.dump_recover_dir = argv[++i];
            c.rec_dump_max = 4;
        }
        else if (!strcmp(argv[i], "--dump-first") && i + 1 < argc) {
            c.dump_first_dir = argv[++i];
            c.first_dump_max = 30;
        }
        else if (!strcmp(argv[i], "--start-gate") && i + 1 < argc) c.start_gate = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--recover-sleep-ms") && i + 1 < argc) c.recover_sleep_ms = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--recv-buf-kb") && i + 1 < argc) c.recv_buf_kb = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--mode") && i + 1 < argc) {
            unsigned w, h, hz;
            if (sscanf(argv[++i], "%ux%u@%u", &w, &h, &hz) != 3) { usage(argv[0]); return 2; }
            c.want_mode = 1; c.want_w = w; c.want_h = h; c.want_hz = hz;
        }
        else if (!strcmp(argv[i], "--video") && i + 1 < argc) {
            if (sscanf(argv[++i], "%ux%u", &c.video_w, &c.video_h) != 2) { usage(argv[0]); return 2; }
        } else { usage(argv[0]); return 2; }
    }

    if (inv) { inventory(); return 0; }
    if (!file && !sock_path) { usage(argv[0]); return 2; }
    if (sock_path && !frames_set) frames = 0;
    if (lat_csv) {
        c.lat_fp = fopen(lat_csv, "a");
        if (!c.lat_fp) { perror(lat_csv); return 2; }
        setvbuf(c.lat_fp, NULL, _IOLBF, 0);
        if (ftell(c.lat_fp) == 0)
            fprintf(c.lat_fp,
                    "frame,seq,present_mono_ns,age_ms,decode_ms,wait_ms,backlog,session\n");
    }

    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);

    if (!no_display) {
        if (drm_setup(&c) < 0) { cleanup(&c); return 1; }
        c.hide_primary = hide_primary;
    }

    if (file) {
        if (read_file(file, &data, &filelen, limit) < 0) return 1;
        printf("input %s bytes=%zu (limit=%zu)\n", file, filelen, limit);
        if (split_annexb(data, filelen, &c.chunk_off, &c.chunk_len, &c.n_chunks) < 0) {
            fprintf(stderr, "no Annex-B start code found\n");
            free(data);
            return 1;
        }
        c.in_data = data;
        c.in_len = filelen;
        printf("annexb AU chunks=%zu\n", c.n_chunks);
    }

    c.video_fd = open("/dev/video0", O_RDWR | O_NONBLOCK);
    if (c.video_fd < 0) { perror("open /dev/video0"); cleanup(&c); free(data); return 1; }

    if (v4l2_subscribe_source_change(&c) < 0) { cleanup(&c); free(data); return 1; }

    int rc;
    if (sock_path) {
        if (v4l2_output_setup_socket(&c) < 0) { cleanup(&c); return 1; }
        c.sock_fd = sock_connect(sock_path);
        if (c.sock_fd < 0) { cleanup(&c); return 1; }
        if (c.recv_buf_kb > 0) {
            int sz = c.recv_buf_kb * 1024;
            if (setsockopt(c.sock_fd, SOL_SOCKET, SO_RCVBUF, &sz, sizeof(sz)) == 0) {
                socklen_t sl = sizeof(sz);
                if (getsockopt(c.sock_fd, SOL_SOCKET, SO_RCVBUF, &sz, &sl) == 0)
                    printf("AU socket SO_RCVBUF=%d (requested %d KB)\n", sz, c.recv_buf_kb);
            } else {
                perror("SO_RCVBUF");
            }
        }
        printf("AU socket connected: %s\n", sock_path);
        rc = run_socket(&c, frames);
    } else {
        if (v4l2_output_setup(&c) < 0) { cleanup(&c); free(data); return 1; }
        if (v4l2_wait_source_change(&c, 5000) < 0) { cleanup(&c); free(data); return 1; }
        if (v4l2_capture_setup(&c) < 0) { cleanup(&c); free(data); return 1; }
        rc = run_decode(&c, frames, no_display);
        if (rc == 0 && !no_display && hold_ms > 0 && c.last_fb) {
            printf("HOLD fb=%u for %d ms (Ctrl-C to stop early)\n", c.last_fb, hold_ms);
            double until = now_ms() + hold_ms;
            while (!g_stop && now_ms() < until) {
                struct timespec ts = { .tv_sec = 0, .tv_nsec = 100 * 1000 * 1000 };
                nanosleep(&ts, NULL);
            }
        }
    }
    printf("STOPPING rc=%d\n", rc);
    cleanup(&c);
    free(c.chunk_off);
    free(c.chunk_len);
    free(data);
    return rc == 0 ? 0 : 1;
}
