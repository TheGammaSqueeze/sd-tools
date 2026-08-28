#version 450
layout(push_constant) uniform PC { uint iters; } pc;
layout(location=0) out vec4 o;
void main(){
  mediump float a=gl_FragCoord.x*0.001, b=gl_FragCoord.y*0.001, c=0.0, d=0.0;
  for(uint i=0u;i<pc.iters;i++){ a=a*b+c; b=b*c+d; c=c*d+a; d=d*a+b; }
  o=vec4(a,b,c,d);
}
