#include "helper.h"

int needs_reorder(int on_hand, int reserved)
{
    return on_hand - reserved <= 3;
}
