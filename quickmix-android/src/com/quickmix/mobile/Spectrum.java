package com.quickmix.mobile;

import java.util.Arrays;

final class Spectrum {
    private static final int WINDOW=2048, BINS=48, MASK=WINDOW-1;
    private final float[] left=new float[WINDOW], right=new float[WINDOW];
    private final double[] weight=new double[WINDOW], cos=new double[WINDOW/2], sin=new double[WINDOW/2];
    private final double[] real=new double[WINDOW], imag=new double[WINDOW], power=new double[WINDOW/2];
    private final int[] reverse=new int[WINDOW], first=new int[BINS], last=new int[BINS];
    private int cursor;
    private boolean original, stereo;

    Spectrum(int rate) {
        for (int i=0;i<WINDOW;i++) {
            weight[i]=.5-.5*Math.cos(2*Math.PI*i/(WINDOW-1));
            reverse[i]=Integer.reverse(i) >>> (32-Integer.numberOfTrailingZeros(WINDOW));
        }
        for (int i=0;i<cos.length;i++) {
            double angle=-2*Math.PI*i/WINDOW;
            cos[i]=Math.cos(angle);
            sin[i]=Math.sin(angle);
        }
        for (int i=0;i<BINS;i++) {
            double lower=20*Math.pow(1000,(i-.5)/(BINS-1));
            double upper=20*Math.pow(1000,(i+.5)/(BINS-1));
            first[i]=Math.max(1,(int)Math.round(lower*WINDOW/rate));
            last[i]=Math.min(power.length-1,(int)Math.round(upper*WINDOW/rate));
        }
    }

    void reset() {
        if (cursor==0) return;
        cursor=0;
        Arrays.fill(left,0);
        Arrays.fill(right,0);
    }

    void add(short[] samples,int length,int channels,boolean original) {
        if (this.original!=original) reset();
        this.original=original;
        stereo=channels==2;
        for (int i=0;i<length;i+=channels) {
            int slot=cursor++&MASK;
            left[slot]=samples[i]/32768f;
            if (stereo) right[slot]=samples[i+1]/32768f;
        }
    }

    private void accumulate(float[] channel) {
        for (int i=0;i<WINDOW;i++) {
            real[reverse[i]]=channel[(cursor+i)&MASK]*weight[i];
            imag[reverse[i]]=0;
        }
        for (int length=2;length<=WINDOW;length*=2) {
            int half=length/2, step=WINDOW/length;
            for (int start=0;start<WINDOW;start+=length) {
                for (int i=0;i<half;i++) {
                    int a=start+i,b=a+half,k=i*step;
                    double re=real[b]*cos[k]-imag[b]*sin[k], im=real[b]*sin[k]+imag[b]*cos[k];
                    real[b]=real[a]-re;
                    imag[b]=imag[a]-im;
                    real[a]+=re;
                    imag[a]+=im;
                }
            }
        }
        for (int i=1;i<power.length;i++) power[i]+=real[i]*real[i]+imag[i]*imag[i];
    }

    float[] read() {
        Arrays.fill(power,0);
        accumulate(left);
        if (stereo) accumulate(right);
        float[] bins=new float[BINS];
        double normalization=(stereo?2:1)*(WINDOW*WINDOW/16.0);
        for (int i=0;i<BINS;i++) {
            double peak=0;
            for (int k=first[i];k<=last[i];k++) peak=Math.max(peak,power[k]);
            double db=10*Math.log10(peak/normalization+1e-10);
            bins[i]=(float)Math.max(0,Math.min(1,1+db/72));
        }
        return bins;
    }
}
