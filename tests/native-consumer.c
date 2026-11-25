#include <stdint.h>
#include <assert.h>
#include "native.h"
int main(void) {
  assert(native_init() == 0);
  for (uint32_t value=0; value<100; value++)
    assert(native_answer(value) == value + EXPECTED);
  assert(native_answer(UINT32_MAX) == (uint32_t)(EXPECTED-1));
  return 0;
}
