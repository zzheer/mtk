#include <stdio.h>
#include <string.h>
#include "process_group.h"
static int generation = 1;
int init_process_iterator(struct process_iterator *it, struct process_filter *filter) { it->i = 0; return 0; }
int get_next_process(struct process_iterator *it, struct process *p) {
    if (it->i++) return -1;
    memset(p, 0, sizeof(*p));
    p->pid = 100; p->starttime = generation; p->cputime = 10;
    return 0;
}
int close_process_iterator(struct process_iterator *it) { return 0; }
int main(void) {
    struct process_group group;
    init_process_group(&group, 100, 1);
    generation = 2;
    update_process_group(&group);
    struct process *p = first_elem(group.proclist);
    int result = p->starttime == 2 ? 0 : 1;
    if (result) fprintf(stderr, "reused PID retains stale creation time\n");
    close_process_group(&group);
    return result;
}
