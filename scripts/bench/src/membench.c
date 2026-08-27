// membench - DDR bandwidth (streaming read + copy) and latency (random cycle
// pointer chase). Buffer >> LLC so it hits DRAM. Anti-elision via volatile sinks.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
static double now(void){ struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec + t.tv_nsec/1e9; }
static volatile uint64_t g_sink;

int main(int argc,char**argv){
  size_t mb = argc>1? (size_t)atoi(argv[1]) : 256;   // buffer MiB (>> LLC ~1-4MB)
  size_t n = mb*1024*1024;
  size_t cnt = n/sizeof(uint64_t);
  uint64_t *a=malloc(n), *b=malloc(n);
  if(!a||!b){printf("alloc fail\n");return 1;}
  for(size_t i=0;i<cnt;i++) a[i]=i*2654435761ULL;
  memset(b,0,n);

  // --- streaming READ bandwidth (sum) ---
  int reps=6; double t0=now(); uint64_t s=0;
  for(int r=0;r<reps;r++) for(size_t i=0;i<cnt;i++) s+=a[i];
  double dt=now()-t0; g_sink=s;
  double read_gbps=((double)n*reps)/1e9/dt;

  // --- COPY bandwidth (read+write) ---
  t0=now();
  for(int r=0;r<reps;r++){ memcpy(b,a,n); }
  dt=now()-t0; g_sink=b[cnt-1];
  double copy_gbps=((double)n*reps*2)/1e9/dt;

  // --- latency: random-cycle pointer chase over cacheline-strided slots ---
  size_t slots = n/64;                 // one node per cacheline
  size_t *perm = malloc(slots*sizeof(size_t));
  for(size_t i=0;i<slots;i++) perm[i]=i;
  for(size_t i=slots-1;i>0;i--){ size_t j=(size_t)((a[i%cnt]^ (i*6364136223846793005ULL))%(i+1)); size_t t=perm[i];perm[i]=perm[j];perm[j]=t; }
  // build the cycle: b[perm[k]*8 slot] -> next
  uint64_t *nodes=b;                   // reuse b as node array (index units of 8 bytes; step 8 = 64 bytes)
  for(size_t k=0;k<slots;k++) nodes[perm[k]*8] = perm[(k+1)%slots]*8;
  size_t steps=40000000; volatile size_t p=0; t0=now();
  for(size_t i=0;i<steps;i++) p=nodes[p];
  dt=now()-t0; g_sink=p;
  double lat_ns=dt/steps*1e9;

  printf("membench buf=%zuMiB read_GBps=%.2f copy_GBps=%.2f latency_ns=%.2f\n",
         mb, read_gbps, copy_gbps, lat_ns);
  free(a);free(b);free(perm); return 0;
}
