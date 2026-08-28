#version 450
#extension GL_EXT_shader_explicit_arithmetic_types_float16 : require
layout(push_constant) uniform PC { uint iters; } pc;
layout(location=0) out vec4 o;
void main(){
  float16_t a=float16_t(gl_FragCoord.x*0.001), b=float16_t(gl_FragCoord.y*0.001), c=float16_t(0.0), d=float16_t(0.0);
  for(uint i=0u;i<pc.iters;i++){ a=a*b+c; b=b*c+d; c=c*d+a; d=d*a+b; }
  o=vec4(float(a),float(b),float(c),float(d));
}
