#include "helper.h"
#include "reorder_policy.h"

int needs_reorder(int on_hand, int reserved)
{
    int threshold = reserved >= LARGE_RESERVATION ? HIGH_RESERVE_BUFFER : NORMAL_BUFFER;
    return on_hand - reserved <= threshold;
}
