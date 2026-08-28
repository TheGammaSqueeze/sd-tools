#version 450
layout(push_constant) uniform PC { uint iters; } pc;
layout(location=0) out vec4 o;
void main(){
  float a=gl_FragCoord.x*0.001, b=gl_FragCoord.y*0.001, c=0.0, d=0.0;
  for(uint i=0u;i<pc.iters;i++){ a=fma(a,b,c); b=fma(b,c,d); c=fma(c,d,a); d=fma(d,a,b); }
  o=vec4(a,b,c,d);
}
