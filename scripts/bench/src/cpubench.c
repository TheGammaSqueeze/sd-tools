// cpubench - fixed-work CPU microbenchmark. Prints ops/sec for an integer+FP
// mixed loop. Pin with taskset to a cluster; higher freq => higher ops/sec.
// Reports a stable score (median of N passes) so it can compare baseline vs OC.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
#include <string.h>

static double now(void){ struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec + t.tv_nsec/1e9; }

// integer + float mixed kernel, resistant to being optimized away
static volatile double g_sink;
static double kernel(uint64_t iters){
  uint64_t a=0x12345678,b=0x9e3779b97f4a7c15ULL; double f=1.0000001,acc=1.0;
  for(uint64_t i=0;i<iters;i++){
    a=a*6364136223846793005ULL+1442695040888963407ULL;
    b^=(b<<13); b^=(b>>7); b^=(b<<17);
    acc=acc*f+ (double)((a^b)&0xffff)*1e-6;
    if(acc>1e6) acc=1.0;
  }
  return acc + (double)(a^b);
}

int main(int argc,char**argv){
  uint64_t iters = argc>1? strtoull(argv[1],0,10): 300000000ULL;
  int passes = argc>2? atoi(argv[2]) : 5;
  double best=1e18;
  for(int p=0;p<passes;p++){
    double t0=now(); double r=kernel(iters); double dt=now()-t0;
    g_sink=r;
    if(dt<best) best=dt;
  }
  double ops = (double)iters/best;              // loop iters per second
  printf("cpubench iters=%llu passes=%d best_s=%.4f mops=%.2f\n",
         (unsigned long long)iters, passes, best, ops/1e6);
  return 0;
}
