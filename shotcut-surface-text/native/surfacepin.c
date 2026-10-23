/* Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
 * True projective corner pin for RGBA title layers. No external dependencies.
 * Coordinates use the frei0r convention (p * 3 - 1) * (dimension - 1).
 */
#include "frei0r.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

typedef struct { unsigned w, h; double p[9]; } Instance;
int f0r_init(void) { return 1; }
void f0r_deinit(void) {}
void f0r_get_plugin_info(f0r_plugin_info_t *i) {
    i->name="SurfacePin"; i->author="Surface Text contributors";
    i->plugin_type=F0R_PLUGIN_TYPE_FILTER; i->color_model=F0R_COLOR_MODEL_RGBA8888;
    i->frei0r_version=1; i->major_version=1; i->minor_version=0; i->num_params=9;
    i->explanation="Projective surface subtitle pin with premultiplied alpha sampling";
}
void f0r_get_param_info(f0r_param_info_t *i, int n) {
    static const char *names[]={"Top left X","Top left Y","Top right X","Top right Y",
        "Bottom right X","Bottom right Y","Bottom left X","Bottom left Y","Opacity"};
    i->name=(n>=0 && n<9)?names[n]:"Invalid"; i->type=F0R_PARAM_DOUBLE;
    i->explanation=n==8?"Opacity; zero hides lost tracking":"Coordinate = (value * 3 - 1) * (dimension - 1)";
}
f0r_instance_t f0r_construct(unsigned w, unsigned h) {
    Instance *s=calloc(1,sizeof(*s)); if(!s) return NULL;
    s->w=w; s->h=h;
    const double initial[]={1./3,1./3,2./3,1./3,2./3,2./3,1./3,2./3,1};
    memcpy(s->p,initial,sizeof(initial)); return s;
}
void f0r_destruct(f0r_instance_t i) { free(i); }
void f0r_set_param_value(f0r_instance_t i,f0r_param_t p,int n) {
    if(n>=0 && n<9) ((Instance*)i)->p[n]=*(double*)p;
}
void f0r_get_param_value(f0r_instance_t i,f0r_param_t p,int n) {
    if(n>=0 && n<9) *(double*)p=((Instance*)i)->p[n];
}
static int solve(double a[8][9],double h[9]) {
    for(int c=0;c<8;c++) {
        int pivot=c;
        for(int r=c+1;r<8;r++) if(fabs(a[r][c])>fabs(a[pivot][c])) pivot=r;
        if(fabs(a[pivot][c])<1e-10) return 0;
        for(int j=c;j<9;j++){double t=a[c][j];a[c][j]=a[pivot][j];a[pivot][j]=t;}
        double k=a[c][c]; for(int j=c;j<9;j++) a[c][j]/=k;
        for(int r=0;r<8;r++) if(r!=c) {
            k=a[r][c]; for(int j=c;j<9;j++) a[r][j]-=k*a[c][j];
        }
    }
    for(int i=0;i<8;i++) h[i]=a[i][8]; h[8]=1; return 1;
}
void f0r_update(f0r_instance_t inst,double time,const uint32_t *in,uint32_t *out) {
    (void)time; Instance *s=inst; const unsigned w=s->w,h=s->h;
    memset(out,0,(size_t)w*h*4);
    if(w<2 || h<2 || !isfinite(s->p[8]) || s->p[8]<=0) return;
    double opacity=fmin(s->p[8],1),q[4][2],a[8][9]={{0}},m[9];
    double uv[4][2]={{0,0},{w-1,0},{w-1,h-1},{0,h-1}};
    for(int i=0;i<4;i++) for(int j=0;j<2;j++) {
        if(!isfinite(s->p[i*2+j]) || s->p[i*2+j]<0 || s->p[i*2+j]>1) return;
        q[i][j]=(s->p[i*2+j]*3-1)*(j?h-1:w-1);
    }
    /* Reject flipped, folded and near-degenerate quadrilaterals. */
    for(int i=0;i<4;i++) {
        int j=(i+1)%4,k=(i+2)%4;
        double cross=(q[j][0]-q[i][0])*(q[k][1]-q[j][1])-(q[j][1]-q[i][1])*(q[k][0]-q[j][0]);
        if(cross<1e-3) return;
    }
    for(int i=0;i<4;i++) {
        double x=q[i][0],y=q[i][1],u=uv[i][0],v=uv[i][1];
        double r1[]={x,y,1,0,0,0,-u*x,-u*y,u};
        double r2[]={0,0,0,x,y,1,-v*x,-v*y,v};
        memcpy(a[2*i],r1,sizeof(r1));memcpy(a[2*i+1],r2,sizeof(r2));
    }
    if(!solve(a,m)) return;
    double minx=q[0][0],maxx=minx,miny=q[0][1],maxy=miny;
    for(int i=1;i<4;i++){minx=fmin(minx,q[i][0]);maxx=fmax(maxx,q[i][0]);miny=fmin(miny,q[i][1]);maxy=fmax(maxy,q[i][1]);}
    int x0=(int)fmax(0,floor(minx)),x1=(int)fmin(w-1,ceil(maxx));
    int y0=(int)fmax(0,floor(miny)),y1=(int)fmin(h-1,ceil(maxy));
    const unsigned char *src=(const unsigned char*)in; unsigned char *dst=(unsigned char*)out;
    for(int y=y0;y<=y1;y++) for(int x=x0;x<=x1;x++) {
        double z=m[6]*x+m[7]*y+1; if(fabs(z)<1e-12) continue;
        double u=(m[0]*x+m[1]*y+m[2])/z,v=(m[3]*x+m[4]*y+m[5])/z;
        if(u< -1e-6 || v< -1e-6 || u>w-1+1e-6 || v>h-1+1e-6) continue;
        u=fmax(0,fmin(w-1,u));v=fmax(0,fmin(h-1,v));
        int ix=(int)u,iy=(int)v,jx=ix+1<(int)w?ix+1:ix,jy=iy+1<(int)h?iy+1:iy;
        double tx=u-ix,ty=v-iy,weight[4]={(1-tx)*(1-ty),tx*(1-ty),tx*ty,(1-tx)*ty};
        size_t pos[4]={((size_t)iy*w+ix)*4,((size_t)iy*w+jx)*4,((size_t)jy*w+jx)*4,((size_t)jy*w+ix)*4};
        double alpha=0,rgb[3]={0};
        for(int j=0;j<4;j++) {
            double aw=src[pos[j]+3]*weight[j];alpha+=aw;
            for(int c=0;c<3;c++) rgb[c]+=src[pos[j]+c]*aw;
        }
        size_t d=((size_t)y*w+x)*4;
        if(alpha>1e-8) {for(int c=0;c<3;c++) dst[d+c]=(unsigned char)fmin(255,floor(rgb[c]/alpha+.5));dst[d+3]=(unsigned char)floor(alpha*opacity+.5);}
    }
}
