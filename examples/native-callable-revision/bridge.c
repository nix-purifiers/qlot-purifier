#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
extern int initialize_lisp(int, char **, char **);
extern char **environ;
uint32_t (*native_answer_cb)(uint32_t);
static int bridge_anchor;
int native_init(void) {
  const char *directory = getenv("QLOT_NATIVE_IMAGE_DIR");
  char marker[PATH_MAX];
  static char core[PATH_MAX];
  if (!directory || directory[0] != '/') return 2;
  if (snprintf(marker, sizeof marker, "%s/identity", directory) >= sizeof marker ||
      snprintf(core, sizeof core, "%s/native.core", directory) >= sizeof core)
    return 2;
  FILE *identity = fopen(marker, "r");
  if (!identity) return 2;
  char actual[sizeof QLOT_PREPARED_IDENTITY + 1];
  int matches = fgets(actual, sizeof actual, identity) &&
                strcmp(actual, QLOT_PREPARED_IDENTITY "\n") == 0 &&
                fgetc(identity) == EOF;
  fclose(identity);
  if (!matches || access(core, R_OK) != 0) return 2;
  Dl_info self;
  if (!dladdr((void*)&bridge_anchor, &self) || !dlopen(self.dli_fname, RTLD_NOW|RTLD_GLOBAL|RTLD_NODELETE)) return 1;
  static char *argv[] = {SDK "/bin/sbcl", "--core",
                        core,
                        "--noinform", "--no-userinit", "--no-sysinit", "--disable-debugger", 0};
  return initialize_lisp(7, argv, environ);
}
uint32_t native_answer(uint32_t value) { return native_answer_cb(value); }
