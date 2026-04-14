#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <cuda_runtime.h>

#define MR 8
#define MG 100
#define PS 64
#define RMS 128
#define TNS 200
#define BLK 128
#define NA PS

typedef struct { int ct,cp,at,ap; } Rule;

__device__ int hp[NA],mn[NA],gd[NA],rm[NA],al[NA],sc[NA],sd[NA];
__device__ int ra[RMS],ri[RMS][8],re[RMS][4];
__device__ Rule dr[PS*MR];
__device__ int dn[PS],ds[PS];

__device__ int cr(int*s){*s=(*s*1103515245+12345)&0x7fffffff;return*s;}

__global__ void isim(int seed){
  int i=blockIdx.x*blockDim.x+threadIdx.x;
  if(i>=NA)return;
  sd[i]=seed+i*137;hp[i]=100;mn[i]=50;gd[i]=10;rm[i]=i%RMS;al[i]=1;sc[i]=i;
}

__global__ void irm(){
  int i=blockIdx.x*blockDim.x+threadIdx.x;
  if(i>=RMS)return;
  ra[i]=0;
  for(int j=0;j<8;j++)ri[i][j]=(i*8+j)%20+1;
  re[i][0]=(i+1)%RMS;re[i][1]=(i-1+RMS)%RMS;
  re[i][2]=(i+RMS/2)%RMS;re[i][3]=(i-RMS/2+RMS)%RMS;
}

__global__ void rgen(int turns){
  int i=blockIdx.x*blockDim.x+threadIdx.x;
  if(i>=NA)return;
  int sid=sc[i],nr=dn[sid];
  for(int t=0;t<turns;t++){
    if(!al[i])break;
    for(int r=0;r<nr;r++){
      int b=sid*MR+r;
      int ct=dr[b].ct,cp=dr[b].cp,at=dr[b].at,ap=dr[b].ap;
      int met=0;
      if(ct==0)met=(hp[i]<cp);
      else if(ct==1)met=(ra[rm[i]]>2);
      else if(ct==2){for(int j=0;j<8;j++)if(ri[rm[i]][j]>0){met=1;break;}}
      else if(ct==3)met=(gd[i]<cp);
      else met=1;
      if(!met)continue;
      if(at==0){atomicSub(&ra[rm[i]],1);rm[i]=re[rm[i]][ap%4];atomicAdd(&ra[rm[i]],1);}
      else if(at==1){int d2=(cr(&sd[i])%10)+1;int rw=(cr(&sd[i])%15)+5;hp[i]-=d2;gd[i]+=rw;}
      else if(at==2){int r2=rm[i];for(int j=0;j<8;j++){if(ri[r2][j]>0){gd[i]+=ri[r2][j];ri[r2][j]=0;break;}}}
      else if(at==3){atomicSub(&ra[rm[i]],1);rm[i]=re[rm[i]][cr(&sd[i])%4];atomicAdd(&ra[rm[i]],1);hp[i]+=5;}
      else if(at==4){hp[i]+=3;mn[i]+=2;}
      else{gd[i]+=(cr(&sd[i])%8);mn[i]-=5;}
      break;
    }
    if(t%10==0){hp[i]+=1;mn[i]+=1;}
    if(hp[i]<=0)al[i]=0;
  }
}

__global__ void sgen(){
  int i=blockIdx.x*blockDim.x+threadIdx.x;
  if(i>=NA)return;
  atomicAdd(&ds[sc[i]],al[i]*500+gd[i]*5+hp[i]*2+mn[i]);
}

__global__ void evol(){
  int i=blockIdx.x*blockDim.x+threadIdx.x;
  if(i>=PS)return;
  ds[i]=0;
  if(i<PS/2)return;
  int p=cr(&sd[i])%(PS/2);
  int b=i*MR,pb=p*MR,pnr=dn[p];
  dn[i]=pnr;
  for(int r=0;r<pnr;r++){
    dr[b+r]=dr[pb+r];
    int m=cr(&sd[i])%5;
    if(m==0)dr[b+r].ct=cr(&sd[i])%5;
    else if(m==1)dr[b+r].cp=cr(&sd[i])%100;
    else if(m==2)dr[b+r].at=cr(&sd[i])%6;
    else if(m==3)dr[b+r].ap=cr(&sd[i])%RMS;
  }
}

int main(){
  printf("=== MUD Arena: Genetic Evolution on Jetson Orin ===\n");
  printf("%d scripts, %d rooms, %d turns, %d gens\n\n",PS,RMS,TNS,MG);
  srand(time(NULL));
  Rule hr[PS*MR]; int hn[PS];
  for(int i=0;i<PS;i++){
    hn[i]=3+(rand()%4);
    for(int r=0;r<hn[i];r++){
      hr[i*MR+r].ct=rand()%5;hr[i*MR+r].cp=rand()%100;
      hr[i*MR+r].at=rand()%6;hr[i*MR+r].ap=rand()%RMS;
    }
  }
  cudaMemcpyToSymbol(dr,hr,sizeof(Rule)*PS*MR);
  cudaMemcpyToSymbol(dn,hn,sizeof(int)*PS);
  int bk=(NA+BLK-1)/BLK,rb=(RMS+BLK-1)/BLK;
  cudaEvent_t s,e;cudaEventCreate(&s);cudaEventCreate(&e);cudaEventRecord(s);
  int be=0,bs=0;
  for(int g=0;g<MG;g++){
    isim<<<bk,BLK>>>(g*1000+42);
    irm<<<rb,BLK>>>();
    cudaDeviceSynchronize();
    int z[RMS];for(int i=0;i<RMS;i++)z[i]=0;
    cudaMemcpyToSymbol(ra,z,sizeof(int)*RMS);
    rgen<<<bk,BLK>>>(TNS);
    cudaDeviceSynchronize();
    int z2[PS];for(int i=0;i<PS;i++)z2[i]=0;
    cudaMemcpyToSymbol(ds,z2,sizeof(int)*PS);
    sgen<<<bk,BLK>>>();
    cudaDeviceSynchronize();
    int hs[PS];cudaMemcpyFromSymbol(hs,ds,sizeof(int)*PS);
    int bt=0,tot=0;
    for(int i=0;i<PS;i++){if(hs[i]>bt){bt=hs[i];bs=i;}tot+=hs[i];}
    if(bt>be)be=bt;
    if(g%10==0||g==MG-1)printf("Gen %3d: best=%d (script %d) avg=%d\n",g,bt,bs,tot/PS);
    if(g<MG-1){evol<<<1,PS>>>();cudaDeviceSynchronize();}
  }
  cudaEventRecord(e);cudaEventSynchronize(e);float ms;cudaEventElapsedTime(&ms,s,e);
  cudaMemcpyFromSymbol(hn,dn,sizeof(int)*PS);
  cudaMemcpyFromSymbol(hr,dr,sizeof(Rule)*PS*MR);
  printf("\n=== Best Script (id %d, score %d) ===\n",bs,be);
  const char*cn[]={"hp_low","enemy","item","gold_low","always"};
  const char*an[]={"move","attack","pickup","flee","wait","trade"};
  for(int r=0;r<hn[bs];r++){
    Rule*ru=&hr[bs*MR+r];
    printf("  IF %s(<%d) THEN %s(%d)\n",cn[ru->ct],ru->cp,an[ru->at],ru->ap);
  }
  printf("\nTime: %.1fms (%.0fus/gen) on Jetson Orin Nano sm_87\n",ms,ms*1000/MG);
  cudaEventDestroy(s);cudaEventDestroy(e);
  return 0;
}
