#version 450
layout(push_constant) uniform PC { uint iters; } pc;
layout(location=0) out vec4 o;
void main(){
  vec2 uv = gl_FragCoord.xy * 0.001;
  vec3 p = vec3(uv, 1.0);
  mat3 m = mat3(0.36,0.48,-0.8, -0.8,0.6,0.0, 0.48,0.64,0.6);
  vec3 acc = vec3(0.0);
  for(uint i=0u;i<pc.iters;i++){
    p = m * p + vec3(0.1,0.2,0.3);
    p = p * 0.5 + 0.5;
    float d = dot(p, vec3(0.33));
    acc += p * d + fract(p*7.0);
    p = normalize(p + acc*0.01);
  }
  o = vec4(acc*0.01, 1.0);
}
