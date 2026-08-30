#version 450
// High-register-pressure fragment bench for lever #3 (wave occupancy). 12
// cross-dependent live accumulators keep regs_count high so the non-fp16
// double-threadsize decision (regs_count*2 <= reg_size_vec4/4) lands in the
// window where GAMMA_WIDE_WAVE (relax to /2) actually flips the chosen wavesize
// - which the low-pressure gamebench/gfxbench shaders never reach. fp32 only
// (matches the nofp16 baseline). Measures whether wider waves help or hurt
// high-pressure shaders like real game fragment shaders.
layout(push_constant) uniform PC { uint iters; } pc;
layout(location=0) out vec4 o;
void main(){
  vec2 p = gl_FragCoord.xy*0.01;
  vec3 a0=vec3(0.1),a1=vec3(0.2),a2=vec3(0.3),a3=vec3(0.4);
  vec3 a4=vec3(0.5),a5=vec3(0.6),a6=vec3(0.7),a7=vec3(0.8);
  vec3 a8=vec3(0.9),a9=vec3(1.0),a10=vec3(0.15),a11=vec3(0.25);
  for(uint i=0u;i<pc.iters;i++){
    float f=float(i);
    a0 += sin(a0*1.1 + p.x + f);
    a1 += cos(a1*1.2 + p.y + f);
    a2 += sin(a2*1.3 + a0.x);
    a3 += cos(a3*1.4 + a1.y);
    a4 += sin(a4*1.5 + a2.z);
    a5 += cos(a5*1.6 + a3.x);
    a6 += sin(a6*1.7 + a4.y);
    a7 += cos(a7*1.8 + a5.z);
    a8 += sin(a8*1.9 + a6.x);
    a9 += cos(a9*2.0 + a7.y);
    a10+= sin(a10*2.1 + a8.z);
    a11+= cos(a11*2.2 + a9.x);
  }
  vec3 s = a0+a1+a2+a3+a4+a5+a6+a7+a8+a9+a10+a11;
  o = vec4(s*0.001, 1.0);
}
