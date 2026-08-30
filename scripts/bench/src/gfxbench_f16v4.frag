#version 450
#extension GL_EXT_shader_explicit_arithmetic_types_float16 : require
layout(push_constant) uniform PC { uint iters; } pc;
layout(location=0) out vec4 o;
void main(){
  // four INDEPENDENT fp16 lanes (a.x/a.y/a.z/a.w each its own dependent chain).
  // vec4 fp16 math should pack into (rpt) half-register ops (2 lanes per reg).
  f16vec4 a = f16vec4(gl_FragCoord.x*0.001, gl_FragCoord.y*0.001, 0.5hf, 0.25hf);
  f16vec4 b = f16vec4(1.0001hf);
  f16vec4 c = f16vec4(0.9999hf);
  for(uint i=0u;i<pc.iters;i++){ a=a*b+c; a=a*c+b; a=a*b+c; a=a*c+b; }
  o=vec4(a);
}
