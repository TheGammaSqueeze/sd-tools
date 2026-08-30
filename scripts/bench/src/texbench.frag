#version 450
layout(set=0,binding=0) uniform sampler2D tex;
layout(push_constant) uniform PC { uint iters; } pc;
layout(location=0) out vec4 o;
void main(){
  vec4 acc=vec4(0.0);
  vec2 base=gl_FragCoord.xy*(1.0/1024.0);
  for(uint i=0u;i<pc.iters;i++){
    float f=float(i)*0.013;
    acc += texture(tex, base + vec2(f, f*0.7));
    acc += texture(tex, base*1.7 + vec2(f*0.3, f));
  }
  o=acc*(1.0/1024.0);
}
