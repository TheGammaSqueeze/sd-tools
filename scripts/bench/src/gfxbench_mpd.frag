#version 450
layout(push_constant) uniform PC { uint iters; } pc;
layout(location=0) out vec4 o;
void main(){
  mediump float a=gl_FragCoord.x*0.001, b=gl_FragCoord.y*0.001;
  mediump float k=1.0000001, m=0.9999999;
  mediump float s0=a,s1=b,s2=a+b,s3=a-b,s4=a*b,s5=a+m,s6=b+k,s7=a*m;
  for(uint i=0u;i<pc.iters;i++){
    s0=s0*k+m; s1=s1*m+k; s2=s2*k+m; s3=s3*m+k;
    s4=s4*k+m; s5=s5*m+k; s6=s6*k+m; s7=s7*m+k;
  }
  o=vec4(s0+s1+s2+s3, s4+s5+s6+s7, 0.0, 1.0);
}
