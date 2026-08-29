#version 450
layout(location=0) in vec2 uv;
layout(location=0) out vec4 o;
layout(binding=0) uniform sampler2D tex;
void main(){
  // sample the previous pass result (RT read-after-write) + a little work
  vec4 c = texture(tex, uv);
  c += texture(tex, uv+vec2(0.003,0.0));
  c += texture(tex, uv+vec2(0.0,0.003));
  o = c*0.34 + vec4(0.001,0.0,0.0,0.0);
}
