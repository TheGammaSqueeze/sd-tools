#version 450
layout(push_constant) uniform PC { uint iters; } pc;
layout(location=0) out vec4 o;
void main(){
  float a=gl_FragCoord.x*0.0007, b=gl_FragCoord.y*0.0011;
  for(uint i=0u;i<pc.iters;i++){ a=clamp(a*1.3-b,0.0,1.0); b=clamp(b*1.3-a,0.0,1.0); a=clamp(a-b*0.7,0.0,1.0); b=clamp(b-a*0.7,0.0,1.0);}
  o=vec4(a,b,a+b,a-b);
}
