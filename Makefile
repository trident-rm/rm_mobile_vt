# Native worker build targets.
# The deployed binary is unstripped and records the source basename in its ELF
# symbol table, so the exact production source must be compiled as d3_probe.c.
CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra
BUILD_DIR ?= build/d3

.PHONY: all exact instrumented clean

all: exact

exact: $(BUILD_DIR)/d3_probe_p128_exact

$(BUILD_DIR)/d3_probe_p128_exact: tools/d3_probe.c
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -o $@ $<

instrumented: $(BUILD_DIR)/d3_probe_p128_instrumented

$(BUILD_DIR)/d3_probe_p128_instrumented: tools/d3_probe_instrumented.c
	@mkdir -p $(BUILD_DIR)
	cp $< $(BUILD_DIR)/d3_probe.c
	$(CC) $(CFLAGS) -o $@ $(BUILD_DIR)/d3_probe.c
	rm -f $(BUILD_DIR)/d3_probe.c

clean:
	rm -f $(BUILD_DIR)/d3_probe_p128_exact $(BUILD_DIR)/d3_probe_p128_instrumented
