// gpubench - Vulkan compute microbenchmark for the Adreno GPU.
// Dispatches an FMA-heavy compute kernel and reports GFLOPS (ALU throughput),
// which both stresses the GPU and measures it. Also a good stability probe.
#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "gpubench_dec_spv.h"
static double now(void){ struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec + t.tv_nsec/1e9; }
#define VK(x) do{ VkResult r=(x); if(r!=VK_SUCCESS){ printf("vk err %d at %s:%d\n",r,__FILE__,__LINE__); exit(1);} }while(0)

int main(int argc,char**argv){
  uint32_t groups = argc>1? (uint32_t)atoi(argv[1]) : 65536;   // workgroups (x64 invocations)
  uint32_t iters  = argc>2? (uint32_t)atoi(argv[2]) : 4096;    // loop iters in shader
  uint32_t reps   = argc>3? (uint32_t)atoi(argv[3]) : 5;
  uint64_t invoc  = (uint64_t)groups*64;

  VkApplicationInfo ai={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.apiVersion=VK_API_VERSION_1_1};
  VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&ai};
  VkInstance inst; VK(vkCreateInstance(&ici,0,&inst));
  uint32_t nd=0; vkEnumeratePhysicalDevices(inst,&nd,0);
  VkPhysicalDevice pds[8]; if(nd>8)nd=8; vkEnumeratePhysicalDevices(inst,&nd,pds);
  VkPhysicalDevice pd=pds[0];
  VkPhysicalDeviceProperties props; vkGetPhysicalDeviceProperties(pd,&props);
  printf("gpu=\"%s\" api=%u.%u.%u\n", props.deviceName,
         VK_VERSION_MAJOR(props.apiVersion),VK_VERSION_MINOR(props.apiVersion),VK_VERSION_PATCH(props.apiVersion));
  // compute queue family
  uint32_t nq=0; vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,0);
  VkQueueFamilyProperties qf[16]; if(nq>16)nq=16; vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,qf);
  uint32_t qfi=0; for(uint32_t i=0;i<nq;i++) if(qf[i].queueFlags&VK_QUEUE_COMPUTE_BIT){qfi=i;break;}
  float prio=1.0f;
  VkDeviceQueueCreateInfo qci={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=qfi,.queueCount=1,.pQueuePriorities=&prio};
  VkDeviceCreateInfo dci={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&qci};
  VkDevice dev; VK(vkCreateDevice(pd,&dci,0,&dev));
  VkQueue q; vkGetDeviceQueue(dev,qfi,0,&q);

  // buffer (one float per invocation)
  VkDeviceSize bsz=invoc*sizeof(float);
  VkBufferCreateInfo bci={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=bsz,.usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
  VkBuffer buf; VK(vkCreateBuffer(dev,&bci,0,&buf));
  VkMemoryRequirements mr; vkGetBufferMemoryRequirements(dev,buf,&mr);
  VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(pd,&mp);
  uint32_t mt=0; for(uint32_t i=0;i<mp.memoryTypeCount;i++) if((mr.memoryTypeBits&(1u<<i))&&(mp.memoryTypes[i].propertyFlags&VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)){mt=i;break;}
  VkMemoryAllocateInfo mai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=mr.size,.memoryTypeIndex=mt};
  VkDeviceMemory mem; VK(vkAllocateMemory(dev,&mai,0,&mem)); VK(vkBindBufferMemory(dev,buf,mem,0));
  void*mapd; VK(vkMapMemory(dev,mem,0,bsz,0,&mapd)); for(uint64_t i=0;i<invoc;i++) ((float*)mapd)[i]=1.0f; vkUnmapMemory(dev,mem);

  // shader + pipeline
  VkShaderModuleCreateInfo smci={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=gpubench_spv_len,.pCode=(const uint32_t*)gpubench_spv};
  VkShaderModule sm; VK(vkCreateShaderModule(dev,&smci,0,&sm));
  VkDescriptorSetLayoutBinding dslb={.binding=0,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT};
  VkDescriptorSetLayoutCreateInfo dslci={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=1,.pBindings=&dslb};
  VkDescriptorSetLayout dsl; VK(vkCreateDescriptorSetLayout(dev,&dslci,0,&dsl));
  VkPushConstantRange pcr={.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT,.offset=0,.size=4};
  VkPipelineLayoutCreateInfo plci={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=1,.pSetLayouts=&dsl,.pushConstantRangeCount=1,.pPushConstantRanges=&pcr};
  VkPipelineLayout pl; VK(vkCreatePipelineLayout(dev,&plci,0,&pl));
  VkComputePipelineCreateInfo cpci={.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
    .stage={.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_COMPUTE_BIT,.module=sm,.pName="main"},.layout=pl};
  VkPipeline pipe; VK(vkCreateComputePipelines(dev,0,1,&cpci,0,&pipe));

  VkDescriptorPoolSize dps={.type=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.descriptorCount=1};
  VkDescriptorPoolCreateInfo dpci={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,.maxSets=1,.poolSizeCount=1,.pPoolSizes=&dps};
  VkDescriptorPool dp; VK(vkCreateDescriptorPool(dev,&dpci,0,&dp));
  VkDescriptorSetAllocateInfo dsai={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=dp,.descriptorSetCount=1,.pSetLayouts=&dsl};
  VkDescriptorSet ds; VK(vkAllocateDescriptorSets(dev,&dsai,&ds));
  VkDescriptorBufferInfo dbi={.buffer=buf,.offset=0,.range=bsz};
  VkWriteDescriptorSet wds={.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=ds,.dstBinding=0,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.pBufferInfo=&dbi};
  vkUpdateDescriptorSets(dev,1,&wds,0,0);

  VkCommandPoolCreateInfo cpci2={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.queueFamilyIndex=qfi};
  VkCommandPool cp; VK(vkCreateCommandPool(dev,&cpci2,0,&cp));
  VkCommandBufferAllocateInfo cbai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=cp,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};
  VkCommandBuffer cb; VK(vkAllocateCommandBuffers(dev,&cbai,&cb));
  VkCommandBufferBeginInfo cbbi={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
  VK(vkBeginCommandBuffer(cb,&cbbi));
  vkCmdBindPipeline(cb,VK_PIPELINE_BIND_POINT_COMPUTE,pipe);
  vkCmdBindDescriptorSets(cb,VK_PIPELINE_BIND_POINT_COMPUTE,pl,0,1,&ds,0,0);
  vkCmdPushConstants(cb,pl,VK_SHADER_STAGE_COMPUTE_BIT,0,4,&iters);
  vkCmdDispatch(cb,groups,1,1);
  VK(vkEndCommandBuffer(cb));

  double best=1e18;
  for(uint32_t r=0;r<reps;r++){
    VkSubmitInfo si={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cb};
    double t0=now(); VK(vkQueueSubmit(q,1,&si,0)); VK(vkQueueWaitIdle(q)); double dt=now()-t0;
    if(dt<best) best=dt;
  }
  double flops=(double)invoc*iters*8.0;   // 4 FMA = 8 flops per loop iter
  printf("gpubench groups=%u iters=%u invoc=%llu best_s=%.4f gflops=%.1f\n",
         groups,iters,(unsigned long long)invoc,best,flops/best/1e9);
  return 0;
}
