// rtbench - multi-pass render-to-texture microbench. Ping-pongs between two images:
// each pass samples the previous pass's result and renders into the other image, with
// a read-after-write barrier between passes. This exercises GMEM tile store/load and
// cache coherency between passes - the DXVK/VKD3D/RPCS3 emulator pattern where
// TU_DEBUG=sysmem / flushall actually matter (unlike single-pass gfxbench). Reports
// passes/s. Args: SIZE PASSES REPS.
#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "rtbench_vert_spv.h"
#include "rtbench_frag_spv.h"
static double now(void){ struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec + t.tv_nsec/1e9; }
#define VK(x) do{ VkResult r=(x); if(r!=VK_SUCCESS){ printf("vk err %d at %d\n",r,__LINE__); exit(1);} }while(0)

int main(int argc,char**argv){
  uint32_t SZ = argc>1?(uint32_t)atoi(argv[1]):512;
  uint32_t PASSES = argc>2?(uint32_t)atoi(argv[2]):600;
  uint32_t reps = argc>3?(uint32_t)atoi(argv[3]):6;

  VkApplicationInfo ai={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.apiVersion=VK_API_VERSION_1_1};
  VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&ai};
  VkInstance inst; VK(vkCreateInstance(&ici,0,&inst));
  uint32_t nd=0; vkEnumeratePhysicalDevices(inst,&nd,0);
  VkPhysicalDevice pds[8]; if(nd>8)nd=8; vkEnumeratePhysicalDevices(inst,&nd,pds);
  VkPhysicalDevice pd=pds[0];
  VkPhysicalDeviceProperties props; vkGetPhysicalDeviceProperties(pd,&props);
  printf("gpu=\"%s\"\n", props.deviceName);
  uint32_t nq=0; vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,0);
  VkQueueFamilyProperties qf[16]; if(nq>16)nq=16; vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,qf);
  uint32_t qfi=0; for(uint32_t i=0;i<nq;i++) if(qf[i].queueFlags&VK_QUEUE_GRAPHICS_BIT){qfi=i;break;}
  float prio=1.0f;
  VkDeviceQueueCreateInfo qci={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=qfi,.queueCount=1,.pQueuePriorities=&prio};
  VkDeviceCreateInfo dci={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&qci};
  VkDevice dev; VK(vkCreateDevice(pd,&dci,0,&dev));
  VkQueue q; vkGetDeviceQueue(dev,qfi,0,&q);
  VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(pd,&mp);

  VkFormat fmt=VK_FORMAT_R8G8B8A8_UNORM;
  VkImage img[2]; VkDeviceMemory mem[2]; VkImageView view[2]; VkFramebuffer fb[2];

  // render pass: load=load (preserve, forces tile load), store=store
  VkAttachmentDescription ad={.format=fmt,.samples=VK_SAMPLE_COUNT_1_BIT,.loadOp=VK_ATTACHMENT_LOAD_OP_LOAD,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,
    .stencilLoadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE,.stencilStoreOp=VK_ATTACHMENT_STORE_OP_DONT_CARE,
    .initialLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,.finalLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
  VkAttachmentReference ar={.attachment=0,.layout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
  VkSubpassDescription sd={.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS,.colorAttachmentCount=1,.pColorAttachments=&ar};
  VkRenderPassCreateInfo rpci={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,.attachmentCount=1,.pAttachments=&ad,.subpassCount=1,.pSubpasses=&sd};
  VkRenderPass rp; VK(vkCreateRenderPass(dev,&rpci,0,&rp));

  for(int i=0;i<2;i++){
    VkImageCreateInfo imci={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.imageType=VK_IMAGE_TYPE_2D,.format=fmt,
      .extent={SZ,SZ,1},.mipLevels=1,.arrayLayers=1,.samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,
      .usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_SAMPLED_BIT,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED};
    VK(vkCreateImage(dev,&imci,0,&img[i]));
    VkMemoryRequirements mr; vkGetImageMemoryRequirements(dev,img[i],&mr);
    uint32_t mt=0; for(uint32_t j=0;j<mp.memoryTypeCount;j++) if((mr.memoryTypeBits&(1u<<j))&&(mp.memoryTypes[j].propertyFlags&VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)){mt=j;break;}
    VkMemoryAllocateInfo mai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=mr.size,.memoryTypeIndex=mt};
    VK(vkAllocateMemory(dev,&mai,0,&mem[i])); VK(vkBindImageMemory(dev,img[i],mem[i],0));
    VkImageViewCreateInfo ivci={.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,.image=img[i],.viewType=VK_IMAGE_VIEW_TYPE_2D,.format=fmt,
      .subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};
    VK(vkCreateImageView(dev,&ivci,0,&view[i]));
    VkFramebufferCreateInfo fbci={.sType=VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,.renderPass=rp,.attachmentCount=1,.pAttachments=&view[i],.width=SZ,.height=SZ,.layers=1};
    VK(vkCreateFramebuffer(dev,&fbci,0,&fb[i]));
  }

  VkSamplerCreateInfo sci={.sType=VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO,.magFilter=VK_FILTER_LINEAR,.minFilter=VK_FILTER_LINEAR,
    .addressModeU=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeV=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.maxLod=1.0f};
  VkSampler samp; VK(vkCreateSampler(dev,&sci,0,&samp));

  VkDescriptorSetLayoutBinding dlb={.binding=0,.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_FRAGMENT_BIT};
  VkDescriptorSetLayoutCreateInfo dlci={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=1,.pBindings=&dlb};
  VkDescriptorSetLayout dsl; VK(vkCreateDescriptorSetLayout(dev,&dlci,0,&dsl));
  VkDescriptorPoolSize dps={.type=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,.descriptorCount=2};
  VkDescriptorPoolCreateInfo dpci={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,.maxSets=2,.poolSizeCount=1,.pPoolSizes=&dps};
  VkDescriptorPool dp; VK(vkCreateDescriptorPool(dev,&dpci,0,&dp));
  VkDescriptorSet ds[2];
  for(int i=0;i<2;i++){
    VkDescriptorSetAllocateInfo dsai={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=dp,.descriptorSetCount=1,.pSetLayouts=&dsl};
    VK(vkAllocateDescriptorSets(dev,&dsai,&ds[i]));
    VkDescriptorImageInfo dii={.sampler=samp,.imageView=view[i],.imageLayout=VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    VkWriteDescriptorSet wds={.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=ds[i],.dstBinding=0,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,.pImageInfo=&dii};
    vkUpdateDescriptorSets(dev,1,&wds,0,0);
  }

  VkShaderModuleCreateInfo vsm={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=rtbench_vert_spv_len,.pCode=(const uint32_t*)rtbench_vert_spv};
  VkShaderModule vs; VK(vkCreateShaderModule(dev,&vsm,0,&vs));
  VkShaderModuleCreateInfo fsm={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=rtbench_frag_spv_len,.pCode=(const uint32_t*)rtbench_frag_spv};
  VkShaderModule fs; VK(vkCreateShaderModule(dev,&fsm,0,&fs));
  VkPipelineLayoutCreateInfo plci={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=1,.pSetLayouts=&dsl};
  VkPipelineLayout pl; VK(vkCreatePipelineLayout(dev,&plci,0,&pl));
  VkPipelineShaderStageCreateInfo st[2]={
    {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_VERTEX_BIT,.module=vs,.pName="main"},
    {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_FRAGMENT_BIT,.module=fs,.pName="main"}};
  VkPipelineVertexInputStateCreateInfo vi={.sType=VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
  VkPipelineInputAssemblyStateCreateInfo ia={.sType=VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,.topology=VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST};
  VkViewport vp={0,0,(float)SZ,(float)SZ,0,1}; VkRect2D scr={{0,0},{SZ,SZ}};
  VkPipelineViewportStateCreateInfo vps={.sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,.viewportCount=1,.pViewports=&vp,.scissorCount=1,.pScissors=&scr};
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
  // both images start COLOR_ATTACHMENT_OPTIMAL
  for(int i=0;i<2;i++){
    VkImageMemoryBarrier b={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED,.newLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
      .srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=img[i],
      .subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1},.dstAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT};
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,0,0,0,0,0,1,&b);
  }
  for(uint32_t p=0;p<PASSES;p++){
    int src=p&1, dst=!src;
    // src: COLOR_ATTACHMENT -> SHADER_READ
    VkImageMemoryBarrier rb={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.oldLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,.newLayout=VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,
      .srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=img[src],
      .subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1},.srcAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT,.dstAccessMask=VK_ACCESS_SHADER_READ_BIT};
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,0,0,0,0,0,1,&rb);
    VkRenderPassBeginInfo rpbi={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,.renderPass=rp,.framebuffer=fb[dst],.renderArea={{0,0},{SZ,SZ}}};
    vkCmdBeginRenderPass(cmd,&rpbi,VK_SUBPASS_CONTENTS_INLINE);
    vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,pipe);
    vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,pl,0,1,&ds[src],0,0);
    vkCmdDraw(cmd,3,1,0,0);
    vkCmdEndRenderPass(cmd);
    // src back to COLOR_ATTACHMENT for reuse
    VkImageMemoryBarrier wb={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.oldLayout=VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,.newLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
      .srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=img[src],
      .subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1},.srcAccessMask=VK_ACCESS_SHADER_READ_BIT,.dstAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT};
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,0,0,0,0,0,1,&wb);
  }
  VK(vkEndCommandBuffer(cmd));

  double best=1e18;
  for(uint32_t r=0;r<reps;r++){
    VkSubmitInfo si={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cmd};
    double t0=now(); VK(vkQueueSubmit(q,1,&si,0)); VK(vkQueueWaitIdle(q)); double dt=now()-t0;
    if(dt<best) best=dt;
  }
  printf("rtbench %ux%u passes=%u best_s=%.5f passes_per_s=%.0f\n",SZ,SZ,PASSES,best,PASSES/best);
  return 0;
}
