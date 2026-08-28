#version 450
layout(push_constant) uniform PC { uint iters; } pc;
layout(location=0) out vec4 o;
void main(){
  vec3 N = normalize(vec3(gl_FragCoord.xy*0.01, 1.0));
  vec3 col = vec3(0.0);
  vec3 base = vec3(0.8,0.6,0.4);
  for(uint i=0u;i<pc.iters;i++){
    vec3 L = normalize(vec3(sin(float(i))*0.5+0.5, cos(float(i))*0.5+0.5, 0.7));
    vec3 V = normalize(vec3(0.2,0.1,1.0));
    vec3 H = normalize(L+V);
    float ndl = max(dot(N,L), 0.0);
    float ndh = max(dot(N,H), 0.0);
    float spec = sin(ndh*6.28)*cos(ndl*6.28) + sin(ndh*3.0);
    col += base*ndl + vec3(spec);
    N = normalize(N + col*0.001);
  }
  o = vec4(col*0.01, 1.0);
}
