/* Kiosk KMS renderer for meson-vdec (GXL).
 *
 * - adapts to the current HDMI mode (or preferred mode if unset)
 * - creates an NV12 V4L2 CAPTURE buffer (EXPBUF -> dmabuf -> PRIME -> ADDFB2)
 * - displays it on the KMS overlay plane with hardware scaling
 * - drops DRM master and disables the plane on exit
 *
 * Usage: kms_render [--dry-run] [--seconds N] [--video WxH]
 *                   [--stdin] [--dumb] [--hide-primary]
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#include <drm/drm.h>
#include <drm/drm_mode.h>

#define FOURCC(a, b, c, d) ((uint32_t)(a) | ((uint32_t)(b) << 8) | ((uint32_t)(c) << 16) | ((uint32_t)(d) << 24))

static volatile sig_atomic_t g_stop = 0;
static void on_signal(int sig) { (void)sig; g_stop = 1; }

struct v4l2_buf {
    int fd;
    void *addr;
    size_t len;
};

struct ctx {
    int card_fd;
    int video_fd;
    int master;
    uint32_t plane_id;
    uint32_t primary_id;
    uint32_t primary_crtc_id;
    uint32_t primary_fb_id;
    uint32_t crtc_id;
    uint32_t fb_id;
    uint32_t handles[2];
    int dmabufs[2];
    struct v4l2_buf bufs[2];
    int have_bufs;
    uint32_t disp_w, disp_h;
    uint32_t video_w, video_h;
    uint32_t dumb_handle;
    size_t dumb_size;
};

static int v4l2_setup(struct ctx *c) {
    struct v4l2_format f;
    memset(&f, 0, sizeof(f));
    f.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
    f.fmt.pix_mp.width = c->video_w;
    f.fmt.pix_mp.height = c->video_h;
    f.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_HEVC;
    f.fmt.pix_mp.field = V4L2_FIELD_NONE;
    f.fmt.pix_mp.num_planes = 1;
    f.fmt.pix_mp.plane_fmt[0].sizeimage = 4 * 1024 * 1024;
    if (ioctl(c->video_fd, VIDIOC_S_FMT, &f) < 0) { perror("S_FMT OUT"); return -1; }

    memset(&f, 0, sizeof(f));
    f.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
    f.fmt.pix_mp.width = c->video_w;
    f.fmt.pix_mp.height = c->video_h;
    f.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_NV12M;
    f.fmt.pix_mp.field = V4L2_FIELD_NONE;
    f.fmt.pix_mp.num_planes = 2;
    if (ioctl(c->video_fd, VIDIOC_S_FMT, &f) < 0) { perror("S_FMT CAP"); return -1; }

    struct v4l2_requestbuffers rb;
    memset(&rb, 0, sizeof(rb));
    rb.count = 1; rb.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE; rb.memory = V4L2_MEMORY_MMAP;
    if (ioctl(c->video_fd, VIDIOC_REQBUFS, &rb) < 0) { perror("REQBUFS"); return -1; }

    for (int p = 0; p < 2; p++) {
        struct v4l2_buffer b;
        struct v4l2_plane planes[VIDEO_MAX_PLANES];
        memset(&b, 0, sizeof(b)); memset(planes, 0, sizeof(planes));
        b.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE; b.memory = V4L2_MEMORY_MMAP; b.index = 0;
        b.m.planes = planes; b.length = 2;
        if (ioctl(c->video_fd, VIDIOC_QUERYBUF, &b) < 0) { perror("QUERYBUF"); return -1; }
        struct v4l2_exportbuffer e;
        memset(&e, 0, sizeof(e));
        e.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE; e.index = 0; e.plane = p; e.flags = O_CLOEXEC;
        if (ioctl(c->video_fd, VIDIOC_EXPBUF, &e) < 0) { perror("EXPBUF"); return -1; }
        c->dmabufs[p] = e.fd;
        c->bufs[p].fd = e.fd;
        c->bufs[p].len = planes[p].length;
        /* dma-buf mmap is not implemented by vb2; use the V4L2 MMAP offset,
         * which maps the same backing memory that was exported above. */
        c->bufs[p].addr = mmap(NULL, planes[p].length, PROT_READ | PROT_WRITE,
                               MAP_SHARED, c->video_fd, planes[p].m.mem_offset);
        if (c->bufs[p].addr == MAP_FAILED) { perror("mmap(v4l2)"); c->bufs[p].addr = NULL; return -1; }
    }
    c->have_bufs = 1;
    return 0;
}

static void fill_pattern(struct ctx *c, int tick) {
    uint8_t *y = c->bufs[0].addr;
    uint8_t *uv = c->bufs[1].addr;
    if (!y || !uv) return;
    uint32_t w = c->video_w, h = c->video_h;
    uint32_t shift = (uint32_t)((tick / 3) % (int)w);
    for (uint32_t row = 0; row < h; row++) {
        for (uint32_t col = 0; col < w; col++) {
            uint32_t x = (col + shift) % w;
            uint8_t val;
            if (x < w / 8) val = 235;           /* white bar */
            else if (x < w / 4) val = 16;       /* black bar */
            else val = (uint8_t)(32 + (x * 180) / w);
            y[row * w + col] = val;
        }
    }
    for (uint32_t row = 0; row < h / 2; row++) {
        for (uint32_t col = 0; col < w / 2; col++) {
            uv[2 * (row * (w / 2) + col)] = 128;
            uv[2 * (row * (w / 2) + col) + 1] = 128;
        }
    }
}

static int drm_setup(struct ctx *c, int dry_run) {
    struct drm_set_client_cap cap = { .capability = DRM_CLIENT_CAP_UNIVERSAL_PLANES, .value = 1 };
    ioctl(c->card_fd, DRM_IOCTL_SET_CLIENT_CAP, &cap);

    struct drm_mode_get_plane_res pr;
    memset(&pr, 0, sizeof(pr));
    if (ioctl(c->card_fd, DRM_IOCTL_MODE_GETPLANERESOURCES, &pr) < 0) { perror("GETPLANERESOURCES"); return -1; }
    uint32_t *planes = calloc(pr.count_planes ? pr.count_planes : 1, sizeof(uint32_t));
    if (!planes) return -1;
    pr.plane_id_ptr = (uint64_t)(uintptr_t)planes;
    if (ioctl(c->card_fd, DRM_IOCTL_MODE_GETPLANERESOURCES, &pr) < 0) { perror("GETPLANERESOURCES2"); free(planes); return -1; }

    int picked = -1;
    for (uint32_t i = 0; i < pr.count_planes; i++) {
        struct drm_mode_get_plane p;
        memset(&p, 0, sizeof(p)); p.plane_id = planes[i];
        if (ioctl(c->card_fd, DRM_IOCTL_MODE_GETPLANE, &p) < 0) continue;
        uint32_t count = p.count_format_types;
        uint32_t *fmts = calloc(count ? count : 1, sizeof(uint32_t));
        p.format_type_ptr = (uint64_t)(uintptr_t)fmts;
        int has_nv12 = 0;
        if (ioctl(c->card_fd, DRM_IOCTL_MODE_GETPLANE, &p) == 0) {
            for (uint32_t k = 0; k < count; k++) {
                if (fmts[k] == FOURCC('N', 'V', '1', '2')) has_nv12 = 1;
            }
        }
        free(fmts);
        if (has_nv12 && picked < 0) picked = (int)planes[i];
        if (!has_nv12 && p.fb_id && p.crtc_id && !c->primary_id) {
            c->primary_id = planes[i];
            c->primary_crtc_id = p.crtc_id;
            c->primary_fb_id = p.fb_id;
        }
    }
    free(planes);
    if (picked < 0) { fprintf(stderr, "no NV12 plane\n"); return -1; }
    c->plane_id = (uint32_t)picked;

    struct drm_mode_card_res res;
    memset(&res, 0, sizeof(res));
    if (ioctl(c->card_fd, DRM_IOCTL_MODE_GETRESOURCES, &res) < 0) { perror("GETRESOURCES"); return -1; }
    uint32_t n_conn = res.count_connectors, n_crtc = res.count_crtcs;
    uint32_t *conns = calloc(n_conn ? n_conn : 1, sizeof(uint32_t));
    uint32_t *crtcs = calloc(n_crtc ? n_crtc : 1, sizeof(uint32_t));
    memset(&res, 0, sizeof(res));
    res.count_connectors = n_conn; res.connector_id_ptr = (uint64_t)(uintptr_t)conns;
    res.count_crtcs = n_crtc; res.crtc_id_ptr = (uint64_t)(uintptr_t)crtcs;
    if (ioctl(c->card_fd, DRM_IOCTL_MODE_GETRESOURCES, &res) < 0) { perror("GETRESOURCES2"); free(conns); free(crtcs); return -1; }

    uint32_t conn_id = 0;
    struct drm_mode_modeinfo chosen;
    memset(&chosen, 0, sizeof(chosen));
    int have_mode = 0;
    for (uint32_t i = 0; i < res.count_connectors; i++) {
        struct drm_mode_get_connector gc;
        memset(&gc, 0, sizeof(gc)); gc.connector_id = conns[i];
        if (ioctl(c->card_fd, DRM_IOCTL_MODE_GETCONNECTOR, &gc) < 0) continue;
        if (gc.connection != 1 /* DRM_MODE_CONNECTED */) continue;
        uint32_t nmodes = gc.count_modes;
        struct drm_mode_modeinfo *modes = calloc(nmodes ? nmodes : 1, sizeof(*modes));
        uint32_t *encs = calloc(gc.count_encoders ? gc.count_encoders : 1, sizeof(uint32_t));
        gc.modes_ptr = (uint64_t)(uintptr_t)modes;
        gc.encoders_ptr = (uint64_t)(uintptr_t)encs;
        gc.count_props = 0; gc.props_ptr = 0;
        if (ioctl(c->card_fd, DRM_IOCTL_MODE_GETCONNECTOR, &gc) < 0) { free(modes); free(encs); continue; }
        for (uint32_t k = 0; k < nmodes; k++) {
            if ((modes[k].type & DRM_MODE_TYPE_PREFERRED) || !have_mode) {
                chosen = modes[k]; have_mode = 1;
                if (modes[k].type & DRM_MODE_TYPE_PREFERRED) break;
            }
        }
        conn_id = conns[i];
        uint32_t enc_id = encs ? encs[0] : 0;
        if (enc_id) {
            struct drm_mode_get_encoder ge;
            memset(&ge, 0, sizeof(ge)); ge.encoder_id = enc_id;
            if (ioctl(c->card_fd, DRM_IOCTL_MODE_GETENCODER, &ge) == 0) c->crtc_id = ge.crtc_id;
        }
        free(modes); free(encs);
        if (have_mode) break;
    }
    free(conns); free(crtcs);
    if (!have_mode || !c->crtc_id) { fprintf(stderr, "no connected connector/mode/crtc\n"); return -1; }

    struct drm_mode_crtc crtc;
    memset(&crtc, 0, sizeof(crtc)); crtc.crtc_id = c->crtc_id;
    if (ioctl(c->card_fd, DRM_IOCTL_MODE_GETCRTC, &crtc) < 0) { perror("GETCRTC"); return -1; }
    if (crtc.mode_valid) {
        c->disp_w = crtc.mode.hdisplay; c->disp_h = crtc.mode.vdisplay;
        printf("current CRTC mode: %ux%u\n", c->disp_w, c->disp_h);
    } else {
        c->disp_w = chosen.hdisplay; c->disp_h = chosen.vdisplay;
        printf("no CRTC mode; preferred: %ux%u (not set in dry-run)\n", c->disp_w, c->disp_h);
    }
    printf("connector=%u crtc=%u plane=%u primary=%u display=%ux%u video=%ux%u\n",
           conn_id, c->crtc_id, c->plane_id, c->primary_id,
           c->disp_w, c->disp_h, c->video_w, c->video_h);
    if (dry_run) return 0;

    if (!crtc.mode_valid) {
        struct drm_mode_crtc sc;
        memset(&sc, 0, sizeof(sc));
        sc.crtc_id = c->crtc_id; sc.fb_id = 0;
        sc.set_connectors_ptr = (uint64_t)(uintptr_t)&conn_id;
        sc.count_connectors = 1;
        sc.mode = chosen; sc.mode_valid = 1;
        if (ioctl(c->card_fd, DRM_IOCTL_MODE_SETCRTC, &sc) < 0) { perror("SETCRTC"); return -1; }
    }
    return 0;
}

static void cleanup(struct ctx *c) {
    if (c->card_fd >= 0 && c->fb_id) {
        struct drm_mode_set_plane sp;
        memset(&sp, 0, sizeof(sp));
        sp.plane_id = c->plane_id; sp.crtc_id = c->crtc_id; sp.fb_id = 0;
        ioctl(c->card_fd, DRM_IOCTL_MODE_SETPLANE, &sp);
        uint32_t fb = c->fb_id; ioctl(c->card_fd, DRM_IOCTL_MODE_RMFB, &fb);
        c->fb_id = 0;
    }
    if (c->card_fd >= 0) {
        for (int p = 0; p < 2; p++) if (c->handles[p]) { struct drm_gem_close gc = { .handle = c->handles[p] }; ioctl(c->card_fd, DRM_IOCTL_GEM_CLOSE, &gc); }
    }
    if (c->have_bufs && c->video_fd >= 0) {
        struct v4l2_requestbuffers rb;
        memset(&rb, 0, sizeof(rb)); rb.count = 0; rb.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE; rb.memory = V4L2_MEMORY_MMAP;
        ioctl(c->video_fd, VIDIOC_REQBUFS, &rb);
    }
    if (c->dumb_handle) {
        if (c->bufs[0].addr) munmap(c->bufs[0].addr, c->dumb_size);
        struct drm_mode_destroy_dumb dd = { .handle = c->dumb_handle };
        ioctl(c->card_fd, DRM_IOCTL_MODE_DESTROY_DUMB, &dd);
        c->dumb_handle = 0;
    }
    for (int p = 0; p < 2; p++) {
        if (!c->dumb_handle && c->bufs[p].addr) munmap(c->bufs[p].addr, c->bufs[p].len);
        if (c->dmabufs[p] >= 0) close(c->dmabufs[p]);
    }
    if (c->card_fd >= 0 && c->master) {
        if (c->primary_id) printf("restoring console via DROP_MASTER\n");
        ioctl(c->card_fd, DRM_IOCTL_DROP_MASTER, 0);
    }
    if (c->video_fd >= 0) close(c->video_fd);
    if (c->card_fd >= 0) close(c->card_fd);
}

int main(int argc, char **argv) {
    struct ctx c;
    memset(&c, 0, sizeof(c));
    c.card_fd = c.video_fd = -1;
    c.dmabufs[0] = c.dmabufs[1] = -1;
    c.video_w = 1920; c.video_h = 1080;
    int dry_run = 0, seconds = 30, stdin_frames = 0, use_dumb = 0, hide_primary = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--dry-run")) dry_run = 1;
        else if (!strcmp(argv[i], "--stdin")) stdin_frames = 1;
        else if (!strcmp(argv[i], "--dumb")) use_dumb = 1;
        else if (!strcmp(argv[i], "--hide-primary")) hide_primary = 1;
        else if (!strcmp(argv[i], "--seconds") && i + 1 < argc) seconds = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--video") && i + 1 < argc) sscanf(argv[++i], "%ux%u", &c.video_w, &c.video_h);
    }

    c.card_fd = open("/dev/dri/card0", O_RDWR);
    if (c.card_fd < 0) { perror("open card0"); return 1; }
    if (!dry_run) {
        int tries = 0;
        while (ioctl(c.card_fd, DRM_IOCTL_SET_MASTER, 0) < 0) {
            if (++tries >= 15) { perror("SET_MASTER (is Xorg running?)"); close(c.card_fd); return 2; }
            usleep(200000);
        }
        c.master = 1;
        if (tries) fprintf(stderr, "SET_MASTER ok after %d retries\n", tries);
    }
    if (drm_setup(&c, dry_run) < 0) { cleanup(&c); return 3; }
    if (dry_run) { cleanup(&c); return 0; }

    struct drm_mode_fb_cmd2 fb;
    memset(&fb, 0, sizeof(fb));
    fb.width = c.video_w; fb.height = c.video_h; fb.pixel_format = FOURCC('N', 'V', '1', '2');
    if (use_dumb) {
        struct drm_mode_create_dumb cd;
        memset(&cd, 0, sizeof(cd));
        cd.width = c.video_w; cd.height = c.video_h * 3 / 2; cd.bpp = 8;
        if (ioctl(c.card_fd, DRM_IOCTL_MODE_CREATE_DUMB, &cd) < 0) { perror("CREATE_DUMB"); cleanup(&c); return 4; }
        struct drm_mode_map_dumb md;
        memset(&md, 0, sizeof(md)); md.handle = cd.handle;
        if (ioctl(c.card_fd, DRM_IOCTL_MODE_MAP_DUMB, &md) < 0) { perror("MAP_DUMB"); cleanup(&c); return 5; }
        void *map = mmap(NULL, cd.size, PROT_READ | PROT_WRITE, MAP_SHARED, c.card_fd, md.offset);
        if (map == MAP_FAILED) { perror("mmap dumb"); cleanup(&c); return 5; }
        c.dumb_handle = cd.handle; c.dumb_size = cd.size;
        c.bufs[0].addr = map;
        c.bufs[1].addr = (uint8_t *)map + (size_t)c.video_w * c.video_h;
        fb.handles[0] = cd.handle; fb.handles[1] = cd.handle;
        fb.pitches[0] = fb.pitches[1] = c.video_w;
        fb.offsets[0] = 0; fb.offsets[1] = (uint32_t)c.video_w * c.video_h;
        printf("DUMB handle=%u size=%llu\n", cd.handle, (unsigned long long)cd.size);
    } else {
        c.video_fd = open("/dev/video0", O_RDWR | O_NONBLOCK);
        if (c.video_fd < 0) { perror("open video0"); cleanup(&c); return 4; }
        if (v4l2_setup(&c) < 0) { cleanup(&c); return 5; }
        for (int p = 0; p < 2; p++) {
            struct drm_prime_handle ph;
            memset(&ph, 0, sizeof(ph)); ph.fd = c.dmabufs[p]; ph.flags = DRM_CLOEXEC;
            if (ioctl(c.card_fd, DRM_IOCTL_PRIME_FD_TO_HANDLE, &ph) < 0) { perror("PRIME"); cleanup(&c); return 6; }
            c.handles[p] = ph.handle;
        }
        fb.handles[0] = c.handles[0]; fb.pitches[0] = c.video_w; fb.offsets[0] = 0;
        fb.handles[1] = c.handles[1]; fb.pitches[1] = c.video_w; fb.offsets[1] = 0;
    }
    if (ioctl(c.card_fd, DRM_IOCTL_MODE_ADDFB2, &fb) < 0) { perror("ADDFB2"); cleanup(&c); return 7; }
    c.fb_id = fb.fb_id;

    signal(SIGINT, on_signal); signal(SIGTERM, on_signal);
    if (hide_primary && c.primary_id && c.primary_fb_id) {
        struct drm_mode_set_plane hp;
        memset(&hp, 0, sizeof(hp));
        hp.plane_id = c.primary_id;
        hp.crtc_id = c.primary_crtc_id;
        hp.fb_id = 0;
        if (ioctl(c.card_fd, DRM_IOCTL_MODE_SETPLANE, &hp) == 0)
            printf("primary plane %u disabled (restored on master drop)\n", c.primary_id);
        else
            perror("SETPLANE primary off");
    }
    struct drm_mode_set_plane sp;
    memset(&sp, 0, sizeof(sp));
    sp.plane_id = c.plane_id; sp.crtc_id = c.crtc_id; sp.fb_id = c.fb_id;
    sp.crtc_x = 0; sp.crtc_y = 0; sp.crtc_w = c.disp_w; sp.crtc_h = c.disp_h;
    sp.src_x = 0; sp.src_y = 0;
    sp.src_w = c.video_w << 16; sp.src_h = c.video_h << 16;
    if (ioctl(c.card_fd, DRM_IOCTL_MODE_SETPLANE, &sp) < 0) { perror("SETPLANE"); cleanup(&c); return 8; }
    printf("PLANE_ON fb=%u src=%ux%u dst=%ux%u (%.1fs)\n", c.fb_id, c.video_w, c.video_h, c.disp_w, c.disp_h, (double)seconds);

    time_t start = time(NULL);
    int tick = 0;
    if (stdin_frames) {
        size_t ysz = (size_t)c.video_w * c.video_h;
        size_t uvsz = (size_t)(c.video_w / 2) * (c.video_h / 2) * 2;
        unsigned long nframes = 0;
        while (!g_stop) {
            if (fread(c.bufs[0].addr, 1, ysz, stdin) != ysz) break;
            if (fread(c.bufs[1].addr, 1, uvsz, stdin) != uvsz) break;
            nframes++;
            if (nframes % 120 == 0) { fprintf(stderr, "kms frames=%lu\n", nframes); fflush(stderr); }
        }
        double dt = (double)(time(NULL) - start);
        printf("STDIN_DONE frames=%lu wall=%.1fs fps=%.2f\n", nframes, dt, dt > 0 ? nframes / dt : 0.0);
    } else {
        while (!g_stop && time(NULL) - start < seconds) {
            fill_pattern(&c, tick++);
            struct timespec ts = { .tv_sec = 0, .tv_nsec = 200 * 1000 * 1000 };
            nanosleep(&ts, NULL);
        }
    }
    printf("stopping\n");
    cleanup(&c);
    return 0;
}
