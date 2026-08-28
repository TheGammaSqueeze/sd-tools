#include <vulkan/vulkan.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define VK(x) do{VkResult r=(x); if(r!=VK_SUCCESS){printf("vk err %d @%d\n",r,__LINE__);exit(1);} }while(0)
int main(){
  VkApplicationInfo ai={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.apiVersion=VK_API_VERSION_1_3};
  uint32_t ic=0; vkEnumerateInstanceExtensionProperties(0,&ic,0);
  VkExtensionProperties* ie=calloc(ic,sizeof(*ie)); vkEnumerateInstanceExtensionProperties(0,&ic,ie);
  const char* iexts[4]; uint32_t ne=0;
  for(uint32_t i=0;i<ic;i++) if(!strcmp(ie[i].extensionName,"VK_KHR_get_physical_device_properties2")) iexts[ne++]=ie[i].extensionName;
  VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&ai,.enabledExtensionCount=ne,.ppEnabledExtensionNames=iexts};
  VkInstance inst; if(vkCreateInstance(&ici,0,&inst)!=VK_SUCCESS){ ici.enabledExtensionCount=0; VK(vkCreateInstance(&ici,0,&inst)); }
  uint32_t nd=0; vkEnumeratePhysicalDevices(inst,&nd,0); VkPhysicalDevice pd; nd=1; vkEnumeratePhysicalDevices(inst,&nd,&pd);
  VkPhysicalDeviceProperties p; vkGetPhysicalDeviceProperties(pd,&p);
  printf("deviceName=%s\n",p.deviceName);
  printf("apiVersion=%u.%u.%u (raw 0x%x)\n",VK_VERSION_MAJOR(p.apiVersion),VK_VERSION_MINOR(p.apiVersion),VK_VERSION_PATCH(p.apiVersion),p.apiVersion);
  printf("driverVersion=0x%x vendorID=0x%x deviceID=0x%x deviceType=%d\n",p.driverVersion,p.vendorID,p.deviceID,p.deviceType);
  // driver properties (1.1 / VK_KHR_driver_properties)
  PFN_vkGetPhysicalDeviceProperties2 gp2=(PFN_vkGetPhysicalDeviceProperties2)vkGetInstanceProcAddr(inst,"vkGetPhysicalDeviceProperties2");
  if(!gp2) gp2=(PFN_vkGetPhysicalDeviceProperties2)vkGetInstanceProcAddr(inst,"vkGetPhysicalDeviceProperties2KHR");
  if(gp2){
    VkPhysicalDeviceDriverProperties dp={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
    VkPhysicalDeviceProperties2 p2={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,.pNext=&dp};
    gp2(pd,&p2);
    printf("driverID=%d driverName=%s driverInfo=%s conformance=%u.%u.%u.%u\n",dp.driverID,dp.driverName,dp.driverInfo,
      dp.conformanceVersion.major,dp.conformanceVersion.minor,dp.conformanceVersion.subminor,dp.conformanceVersion.patch);
  } else printf("(no properties2 - device is Vulkan 1.0 only)\n");
  // key features
  VkPhysicalDeviceFeatures f; vkGetPhysicalDeviceFeatures(pd,&f);
  printf("feat: geometryShader=%d tessellation=%d fragmentStoresAndAtomics=%d shaderStorageImageExtendedFormats=%d textureCompressionASTC_LDR=%d textureCompressionBC=%d multiViewport=%d shaderInt16=%d\n",
    f.geometryShader,f.tessellationShader,f.fragmentStoresAndAtomics,f.shaderStorageImageExtendedFormats,f.textureCompressionASTC_LDR,f.textureCompressionBC,f.multiViewport,f.shaderInt16);
  // extension count + a few 3dmark-relevant ones
  uint32_t ec=0; vkEnumerateDeviceExtensionProperties(pd,0,&ec,0);
  VkExtensionProperties* ee=calloc(ec,sizeof(*ee)); vkEnumerateDeviceExtensionProperties(pd,0,&ec,ee);
  printf("device_extensions=%u\n",ec);
  const char* want[]={"VK_KHR_swapchain","VK_EXT_astc_decode_mode","VK_KHR_shader_float16_int8","VK_KHR_16bit_storage","VK_EXT_descriptor_indexing","VK_KHR_timeline_semaphore","VK_KHR_synchronization2","VK_KHR_maintenance4"};
  for(unsigned i=0;i<sizeof(want)/sizeof(*want);i++){int has=0;for(uint32_t j=0;j<ec;j++)if(!strcmp(ee[j].extensionName,want[i]))has=1;printf("  ext %s = %d\n",want[i],has);}
  printf("limits: maxImageDimension2D=%u maxComputeWorkGroupInvocations=%u maxPushConstantsSize=%u\n",p.limits.maxImageDimension2D,p.limits.maxComputeWorkGroupInvocations,p.limits.maxPushConstantsSize);
  return 0;
}
