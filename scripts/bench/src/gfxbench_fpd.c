// gfxbench - Vulkan GRAPHICS (fragment) microbenchmark for the Adreno GPU.
// Renders a fullscreen triangle to an offscreen target; the fragment shader does
// an FMA loop per pixel, so this exercises the real graphics path (vertex assembly,
// rasterization, fragment shading) rather than pure compute. Reports fragment
// GFLOPS + Mpixels/s, comparable to gpubench's compute GFLOPS. Args: W H iters reps.
#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "gfxbench_vert_spv.h"
#include "gfxbench_fpd_frag_spv.h"
static double now(void){ struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec + t.tv_nsec/1e9; }
#define VK(x) do{ VkResult r=(x); if(r!=VK_SUCCESS){ printf("vk err %d at %s:%d\n",r,__FILE__,__LINE__); exit(1);} }while(0)

int main(int argc,char**argv){
  uint32_t W = argc>1?(uint32_t)atoi(argv[1]):1920;
  uint32_t H = argc>2?(uint32_t)atoi(argv[2]):1080;
  uint32_t iters = argc>3?(uint32_t)atoi(argv[3]):512;
  uint32_t reps  = argc>4?(uint32_t)atoi(argv[4]):5;

  VkApplicationInfo ai={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.apiVersion=VK_API_VERSION_1_1};
  VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&ai};
  VkInstance inst; VK(vkCreateInstance(&ici,0,&inst));
  uint32_t nd=0; vkEnumeratePhysicalDevices(inst,&nd,0);
  VkPhysicalDevice pds[8]; if(nd>8)nd=8; vkEnumeratePhysicalDevices(inst,&nd,pds);
  VkPhysicalDevice pd=pds[0];
  VkPhysicalDeviceProperties props; vkGetPhysicalDeviceProperties(pd,&props);
  printf("gpu=\"%s\" api=%u.%u.%u\n", props.deviceName,
         VK_VERSION_MAJOR(props.apiVersion),VK_VERSION_MINOR(props.apiVersion),VK_VERSION_PATCH(props.apiVersion));
  uint32_t nq=0; vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,0);
  VkQueueFamilyProperties qf[16]; if(nq>16)nq=16; vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,qf);
  uint32_t qfi=0; for(uint32_t i=0;i<nq;i++) if(qf[i].queueFlags&VK_QUEUE_GRAPHICS_BIT){qfi=i;break;}
  float prio=1.0f;
  VkDeviceQueueCreateInfo qci={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=qfi,.queueCount=1,.pQueuePriorities=&prio};
  VkDeviceCreateInfo dci={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&qci};
  VkDevice dev; VK(vkCreateDevice(pd,&dci,0,&dev));
  VkQueue q; vkGetDeviceQueue(dev,qfi,0,&q);

  // offscreen color image
  VkFormat fmt=VK_FORMAT_R8G8B8A8_UNORM;
  VkImageCreateInfo imci={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.imageType=VK_IMAGE_TYPE_2D,.format=fmt,
    .extent={W,H,1},.mipLevels=1,.arrayLayers=1,.samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,
    .usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED};
  VkImage img; VK(vkCreateImage(dev,&imci,0,&img));
  VkMemoryRequirements mr; vkGetImageMemoryRequirements(dev,img,&mr);
  VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(pd,&mp);
  uint32_t mt=0; for(uint32_t i=0;i<mp.memoryTypeCount;i++) if((mr.memoryTypeBits&(1u<<i))&&(mp.memoryTypes[i].propertyFlags&VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)){mt=i;break;}
  VkMemoryAllocateInfo mai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=mr.size,.memoryTypeIndex=mt};
  VkDeviceMemory mem; VK(vkAllocateMemory(dev,&mai,0,&mem)); VK(vkBindImageMemory(dev,img,mem,0));
  VkImageViewCreateInfo ivci={.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,.image=img,.viewType=VK_IMAGE_VIEW_TYPE_2D,.format=fmt,
    .subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};
  VkImageView iv; VK(vkCreateImageView(dev,&ivci,0,&iv));

  // render pass
  VkAttachmentDescription ad={.format=fmt,.samples=VK_SAMPLE_COUNT_1_BIT,.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,
    .stencilLoadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE,.stencilStoreOp=VK_ATTACHMENT_STORE_OP_DONT_CARE,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED,.finalLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
  VkAttachmentReference ar={.attachment=0,.layout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
  VkSubpassDescription sd={.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS,.colorAttachmentCount=1,.pColorAttachments=&ar};
  VkRenderPassCreateInfo rpci={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,.attachmentCount=1,.pAttachments=&ad,.subpassCount=1,.pSubpasses=&sd};
  VkRenderPass rp; VK(vkCreateRenderPass(dev,&rpci,0,&rp));
  VkFramebufferCreateInfo fbci={.sType=VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,.renderPass=rp,.attachmentCount=1,.pAttachments=&iv,.width=W,.height=H,.layers=1};
  VkFramebuffer fb; VK(vkCreateFramebuffer(dev,&fbci,0,&fb));

  // shaders
  VkShaderModuleCreateInfo vsm={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=gfx_vert_spv_len,.pCode=(const uint32_t*)gfx_vert_spv};
  VkShaderModule vs; VK(vkCreateShaderModule(dev,&vsm,0,&vs));
  VkShaderModuleCreateInfo fsm={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=gfx_frag_spv_len,.pCode=(const uint32_t*)gfx_frag_spv};
  VkShaderModule fs; VK(vkCreateShaderModule(dev,&fsm,0,&fs));

  VkPushConstantRange pcr={.stageFlags=VK_SHADER_STAGE_FRAGMENT_BIT,.offset=0,.size=4};
  VkPipelineLayoutCreateInfo plci={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.pushConstantRangeCount=1,.pPushConstantRanges=&pcr};
  VkPipelineLayout pl; VK(vkCreatePipelineLayout(dev,&plci,0,&pl));

  VkPipelineShaderStageCreateInfo st[2]={
    {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_VERTEX_BIT,.module=vs,.pName="main"},
    {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_FRAGMENT_BIT,.module=fs,.pName="main"}};
  VkPipelineVertexInputStateCreateInfo vi={.sType=VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
  VkPipelineInputAssemblyStateCreateInfo ia={.sType=VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,.topology=VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST};
  VkViewport vp={0,0,(float)W,(float)H,0,1}; VkRect2D sc={{0,0},{W,H}};
  VkPipelineViewportStateCreateInfo vps={.sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,.viewportCount=1,.pViewports=&vp,.scissorCount=1,.pScissors=&sc};
  VkPipelineRasterizationStateCreateInfo rs={.sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,.polygonMode=VK_POLYGON_MODE_FILL,.cullMode=VK_CULL_MODE_NONE,.frontFace=VK_FRONT_FACE_COUNTER_CLOCKWISE,.lineWidth=1.0f};
  VkPipelineMultisampleStateCreateInfo ms={.sType=VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT};
  VkPipelineColorBlendAttachmentState cba={.colorWriteMask=0xf};
  VkPipelineColorBlendStateCreateInfo cb={.sType=VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,.attachmentCount=1,.pAttachments=&cba};
  VkGraphicsPipelineCreateInfo gpci={.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,.stageCount=2,.pStages=st,
    .pVertexInputState=&vi,.pInputAssemblyState=&ia,.pViewportState=&vps,.pRasterizationState=&rs,.pMultisampleState=&ms,.pColorBlendState=&cb,.layout=pl,.renderPass=rp,.subpass=0};
  VkPipeline pipe; VK(vkCreateGraphicsPipelines(dev,0,1,&gpci,0,&pipe));

  VkCommandPoolCreateInfo cpci={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.queueFamilyIndex=qfi};
  VkCommandPool cp; VK(vkCreateCommandPool(dev,&cpci,0,&cp));
  VkCommandBufferAllocateInfo cbai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=cp,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};
  VkCommandBuffer cmd; VK(vkAllocateCommandBuffers(dev,&cbai,&cmd));
  VkCommandBufferBeginInfo cbbi={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
  VK(vkBeginCommandBuffer(cmd,&cbbi));
  VkClearValue clr={.color={{0,0,0,1}}};
  VkRenderPassBeginInfo rpbi={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,.renderPass=rp,.framebuffer=fb,.renderArea={{0,0},{W,H}},.clearValueCount=1,.pClearValues=&clr};
  vkCmdBeginRenderPass(cmd,&rpbi,VK_SUBPASS_CONTENTS_INLINE);
  vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,pipe);
  vkCmdPushConstants(cmd,pl,VK_SHADER_STAGE_FRAGMENT_BIT,0,4,&iters);
  vkCmdDraw(cmd,3,1,0,0);
  vkCmdEndRenderPass(cmd);
  VK(vkEndCommandBuffer(cmd));

  double best=1e18;
  for(uint32_t r=0;r<reps;r++){
    VkSubmitInfo si={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cmd};
    double t0=now(); VK(vkQueueSubmit(q,1,&si,0)); VK(vkQueueWaitIdle(q)); double dt=now()-t0;
    if(dt<best) best=dt;
  }
  double pix=(double)W*H;
  double flops=pix*iters*8.0;
  printf("gfxbench %ux%u iters=%u best_s=%.5f gflops=%.1f mpix_per_s=%.1f\n",
         W,H,iters,best,flops/best/1e9,pix/best/1e6);
  return 0;
}
