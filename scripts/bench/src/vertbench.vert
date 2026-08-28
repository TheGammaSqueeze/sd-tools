#version 450
// Vertex-bound microbench: heavy per-vertex transform loop, no vertex buffer
// (positions generated from gl_VertexIndex). Fragment/raster kept negligible by
// a tiny render target + degenerate coverage. push-constant iters controls load.
layout(push_constant) uniform PC { int iters; } pc;
void main(){
  float t = float(gl_VertexIndex) * 0.001;
  vec4 p = vec4(sin(t), cos(t), t*0.01, 1.0);
  // heavy transform chain (mat-like FMA + trig), fp32 by default; fp16 under GAMMA_FP16_VERTEX
  vec3 a = vec3(t, t*1.3, t*0.7);
  for(int i=0;i<pc.iters;i++){
    a = normalize(a * 1.001 + vec3(0.5,0.25,0.125));
    p.xyz = p.xyz * 0.999 + a * 0.001;
    p.x = fma(p.x, 1.0001, sin(a.y));
    p.y = fma(p.y, 0.9999, cos(a.x));
    p.z = fma(p.z, 1.0000, a.z);
  }
  // collapse to a fixed clip point so raster coverage is ~1 pixel
  gl_Position = vec4(fract(p.x)*0.001, fract(p.y)*0.001, 0.0, 1.0);
}
