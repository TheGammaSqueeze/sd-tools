// dynbench - Vulkan per-draw DESCRIPTOR-SET-bind CPU-overhead microbench for the
// Turnip driver. Like drawbench, but each draw first binds a descriptor set
// (alternating between two sets so the descriptor state re-emits every draw) -
// the actual DXVK/VKD3D per-draw hot path (they bind descriptor sets every draw),
// which drawbench's push-constant-only loop never exercised. GPU work is
// negligible (32x32 RT, trivial triangle) so wall-clock is dominated by Turnip's
// descriptor-bind + state-emission CPU cost. Governor-independent. Compare
// us_per_draw against drawbench (push-const only) to isolate the descriptor cost.
// Args: DRAWS reps.
#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "vertbench_vert_spv.h"
#include "vertbench_frag_spv.h"
static double now(void){ struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec + t.tv_nsec/1e9; }
#define VK(x) do{ VkResult r=(x); if(r!=VK_SUCCESS){ printf("vk err %d at %s:%d\n",r,__FILE__,__LINE__); exit(1);} }while(0)

int main(int argc,char**argv){
  uint32_t DRAWS = argc>1?(uint32_t)atoi(argv[1]):20000;
  uint32_t reps  = argc>2?(uint32_t)atoi(argv[2]):10;
  const uint32_t W=32,H=32;

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
  VkImageCreateInfo imci={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.imageType=VK_IMAGE_TYPE_2D,.format=fmt,
    .extent={W,H,1},.mipLevels=1,.arrayLayers=1,.samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,
    .usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED};
  VkImage img; VK(vkCreateImage(dev,&imci,0,&img));
  VkMemoryRequirements mr; vkGetImageMemoryRequirements(dev,img,&mr);
  uint32_t mt=0; for(uint32_t i=0;i<mp.memoryTypeCount;i++) if((mr.memoryTypeBits&(1u<<i))&&(mp.memoryTypes[i].propertyFlags&VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)){mt=i;break;}
  VkMemoryAllocateInfo mai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=mr.size,.memoryTypeIndex=mt};
  VkDeviceMemory mem; VK(vkAllocateMemory(dev,&mai,0,&mem)); VK(vkBindImageMemory(dev,img,mem,0));
  VkImageViewCreateInfo ivci={.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,.image=img,.viewType=VK_IMAGE_VIEW_TYPE_2D,.format=fmt,
    .subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};
  VkImageView iv; VK(vkCreateImageView(dev,&ivci,0,&iv));

  VkAttachmentDescription adsc={.format=fmt,.samples=VK_SAMPLE_COUNT_1_BIT,.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,
    .stencilLoadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE,.stencilStoreOp=VK_ATTACHMENT_STORE_OP_DONT_CARE,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED,.finalLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
  VkAttachmentReference ar={.attachment=0,.layout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
  VkSubpassDescription sd={.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS,.colorAttachmentCount=1,.pColorAttachments=&ar};
  VkRenderPassCreateInfo rpci={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,.attachmentCount=1,.pAttachments=&adsc,.subpassCount=1,.pSubpasses=&sd};
  VkRenderPass rp; VK(vkCreateRenderPass(dev,&rpci,0,&rp));
  VkFramebufferCreateInfo fbci={.sType=VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,.renderPass=rp,.attachmentCount=1,.pAttachments=&iv,.width=W,.height=H,.layers=1};
  VkFramebuffer fb; VK(vkCreateFramebuffer(dev,&fbci,0,&fb));

  // Two small uniform buffers + two descriptor sets to alternate per draw.
  VkBuffer ubo[2]; VkDeviceMemory ubm[2];
  for(int i=0;i<2;i++){
    VkBufferCreateInfo bci={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=256,.usage=VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
    VK(vkCreateBuffer(dev,&bci,0,&ubo[i]));
    VkMemoryRequirements br; vkGetBufferMemoryRequirements(dev,ubo[i],&br);
    uint32_t bt=0; for(uint32_t j=0;j<mp.memoryTypeCount;j++) if((br.memoryTypeBits&(1u<<j))&&(mp.memoryTypes[j].propertyFlags&VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)){bt=j;break;}
    VkMemoryAllocateInfo bmi={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=br.size,.memoryTypeIndex=bt};
    VK(vkAllocateMemory(dev,&bmi,0,&ubm[i])); VK(vkBindBufferMemory(dev,ubo[i],ubm[i],0));
  }
  VkDescriptorSetLayoutBinding dlb={.binding=0,.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_VERTEX_BIT};
  VkDescriptorSetLayoutCreateInfo dlci={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=1,.pBindings=&dlb};
  VkDescriptorSetLayout dsl; VK(vkCreateDescriptorSetLayout(dev,&dlci,0,&dsl));
  VkDescriptorPoolSize dps={.type=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,.descriptorCount=2};
  VkDescriptorPoolCreateInfo dpci={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,.maxSets=2,.poolSizeCount=1,.pPoolSizes=&dps};
  VkDescriptorPool dp; VK(vkCreateDescriptorPool(dev,&dpci,0,&dp));
  VkDescriptorSet ds[2];
  for(int i=0;i<2;i++){
    VkDescriptorSetAllocateInfo dsai={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=dp,.descriptorSetCount=1,.pSetLayouts=&dsl};
    VK(vkAllocateDescriptorSets(dev,&dsai,&ds[i]));
    VkDescriptorBufferInfo dbi={.buffer=ubo[i],.offset=0,.range=256};
    VkWriteDescriptorSet w={.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=ds[i],.dstBinding=0,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,.pBufferInfo=&dbi};
    vkUpdateDescriptorSets(dev,1,&w,0,0);
  }

  VkShaderModuleCreateInfo vsm={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=sizeof(vertbench_vert_spv),.pCode=vertbench_vert_spv};
  VkShaderModule vs; VK(vkCreateShaderModule(dev,&vsm,0,&vs));
  VkShaderModuleCreateInfo fsm={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=sizeof(vertbench_frag_spv),.pCode=vertbench_frag_spv};
  VkShaderModule fs; VK(vkCreateShaderModule(dev,&fsm,0,&fs));

  VkPushConstantRange pcr={.stageFlags=VK_SHADER_STAGE_VERTEX_BIT,.offset=0,.size=4};
  VkPipelineLayoutCreateInfo plci={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=1,.pSetLayouts=&dsl,.pushConstantRangeCount=1,.pPushConstantRanges=&pcr};
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
  VkDynamicState dynstates[2]={VK_DYNAMIC_STATE_VIEWPORT,VK_DYNAMIC_STATE_SCISSOR};
  VkPipelineDynamicStateCreateInfo dyn={.sType=VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,.dynamicStateCount=2,.pDynamicStates=dynstates};
  VkGraphicsPipelineCreateInfo gpci={.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,.stageCount=2,.pStages=st,
    .pVertexInputState=&vi,.pInputAssemblyState=&ia,.pViewportState=&vps,.pRasterizationState=&rs,.pMultisampleState=&ms,.pColorBlendState=&cb,.pDynamicState=&dyn,.layout=pl,.renderPass=rp,.subpass=0};
  VkPipeline pipe; VK(vkCreateGraphicsPipelines(dev,0,1,&gpci,0,&pipe));

  VkCommandPoolCreateInfo cpci={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
    .flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,.queueFamilyIndex=qfi};
  VkCommandPool cp; VK(vkCreateCommandPool(dev,&cpci,0,&cp));
  VkCommandBufferAllocateInfo cbai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=cp,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};
  VkCommandBuffer cmd; VK(vkAllocateCommandBuffers(dev,&cbai,&cmd));
  int32_t iters=1;
  VkClearValue clr={.color={{0,0,0,1}}};
  VkRenderPassBeginInfo rpbi={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,.renderPass=rp,.framebuffer=fb,.renderArea={{0,0},{W,H}},.clearValueCount=1,.pClearValues=&clr};

  double best=1e18;
  for(uint32_t r=0;r<reps+1;r++){
    double t0=now();
    VK(vkResetCommandBuffer(cmd,0));
    VkCommandBufferBeginInfo cbbi={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    VK(vkBeginCommandBuffer(cmd,&cbbi));
    vkCmdBeginRenderPass(cmd,&rpbi,VK_SUBPASS_CONTENTS_INLINE);
    vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,pipe);
    iters=1; vkCmdPushConstants(cmd,pl,VK_SHADER_STAGE_VERTEX_BIT,0,4,&iters);
    for(uint32_t d=0;d<DRAWS;d++){
      vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,pl,0,1,&ds[d&1],0,0); // alternate -> re-emit
      /* per-draw dynamic-state churn (viewport + scissor), the DXVK hot path */
      VkViewport dvp={0,0,(float)(W-(d&1)),(float)H,0,1};
      VkRect2D dsc={{0,0},{W-(d&1),H}};
      vkCmdSetViewport(cmd,0,1,&dvp);
      vkCmdSetScissor(cmd,0,1,&dsc);
      vkCmdDraw(cmd,3,1,0,0);
    }
    vkCmdEndRenderPass(cmd);
    VK(vkEndCommandBuffer(cmd));
    VkSubmitInfo si={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cmd};
    VK(vkQueueSubmit(q,1,&si,0)); VK(vkQueueWaitIdle(q));
    double dt=now()-t0;
    if(r>0 && dt<best) best=dt;
  }
  printf("dynbench draws=%u best_s=%.5f draws_per_s=%.0f us_per_draw=%.3f\n",
         DRAWS,best,(double)DRAWS/best,best/(double)DRAWS*1e6);
  return 0;
}
