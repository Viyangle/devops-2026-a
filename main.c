#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>

#include "config.h"
#include "helper.h"

static int read_quantity(const char *text, int *quantity)
{
    char *end;
    errno = 0;
    long parsed = strtol(text, &end, 10);
    if (errno || end == text || *end || parsed < 0 || parsed > INT_MAX) {
        return 0;
    }
    *quantity = (int)parsed;
    return 1;
}

int main(int argc, char *argv[])
{
    int on_hand = 4;
    int reserved = 2;
    if (argc != 1 &&
        (argc != 3 || !read_quantity(argv[1], &on_hand) ||
         !read_quantity(argv[2], &reserved))) {
        fputs("Usage: app [on-hand reserved]\n", stderr);
        return 2;
    }
    printf("%d\n", needs_reorder(on_hand, reserved) ? VALUE : 0);
    return 0;
}
