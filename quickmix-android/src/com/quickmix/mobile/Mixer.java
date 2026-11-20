package com.quickmix.mobile;

import java.util.Arrays;

final class Mixer {
    static final class Settings {
        // Cleanup, room suppression, presence, leveling, detail, threshold,
        // attack, release, output gain, saturation, followed by six EQ bands.
        final float[] values = {0.35f,0.25f,0.30f,0.35f,0.18f,-18,15,120,0,0.15f,
            70,0,0,-30,0,0, 160,0,0,-30,0,0, 400,0,0,-30,0,0,
            1000,0,0,-30,0,0, 3000,0,0,-30,0,0, 8500,0,0,-30,0,0};
        Settings copy() {
            Settings result = new Settings();
            System.arraycopy(values, 0, result.values, 0, values.length);
            return result;
        }
    }

    static final class Filter {
        double b0=1,b1,b2,a1,a2,x1,x2,y1,y2;
        Filter tune(int mode, double hz, double gain, double rate) {
            double w=2*Math.PI*Math.min(hz,rate*0.46)/rate, c=Math.cos(w);
            double alpha=Math.sin(w)/1.41421356, a=Math.pow(10,gain/40), d=1+alpha;
            if (mode==0) {
                d=1+alpha/a;
                b0=(1+alpha*a)/d; b1=-2*c/d; b2=(1-alpha*a)/d;
                a2=(1-alpha/a)/d;
            } else if (mode==1 || mode==2) {
                b0=(mode==1 ? 1+c : 1-c)/2/d;
                b1=(mode==1 ? -2 : 2)*b0; b2=b0; a2=(1-alpha)/d;
            } else {
                b0=alpha/d; b1=0; b2=-b0; a2=(1-alpha)/d;
            }
            a1=-2*c/d;
            return this;
        }
        double tick(double x) {
            double y=b0*x+b1*x1+b2*x2-a1*y1-a2*y2;
            x2=x1; x1=x; y2=y1; y1=y;
            return y;
        }
        void response(double hz, double rate, double[] result) {
            double w=2*Math.PI*hz/rate, c=Math.cos(w), s=Math.sin(w);
            double nr=b0+b1*c+b2*Math.cos(2*w), ni=b1*s+b2*Math.sin(2*w);
            double dr=1+a1*c+a2*Math.cos(2*w), di=a1*s+a2*Math.sin(2*w);
            double denominator=dr*dr+di*di;
            result[0]=(nr*dr+ni*di)/denominator;
            result[1]=(ni*dr-nr*di)/denominator;
        }
    }

    private final int rate;
    private final Lane[] lanes;
    private final double[] bandPower = new double[6], dynamicCut = new double[6];
    private final float[] dynamicDb=new float[6];
    private final double rmsStep, turnDownStep, turnUpStep;
    private double fast, slow, floor=0.0001, comp=1, level=1, levelPower, levelTarget=1, limiter=1;
    private double attack, release, trim;
    private Settings settings;
    private int counter;

    private static final class Lane {
        final Filter low = new Filter(), presence = new Filter();
        final Filter[] eq = new Filter[6], detector = new Filter[6], dynamicBand = new Filter[6];
        final float[][] echo = new float[6][];
        final int[] cursor = new int[6];
        Lane(int rate) {
            low.tune(1,75,0,rate);
            presence.tune(0,3200,0,rate);
            for (int i=0;i<6;i++) {
                eq[i]=new Filter();
                detector[i]=new Filter();
                dynamicBand[i]=new Filter();
                echo[i]=new float[Math.max(1,rate*(31+i*8)/1000)];
            }
        }
    }

    Mixer(int rate, int channels) {
        this.rate=rate;
        rmsStep=1-coefficient(90);
        turnDownStep=1-coefficient(85);
        turnUpStep=1-coefficient(260);
        lanes=new Lane[channels];
        Arrays.setAll(lanes,i -> new Lane(rate));
    }
    private double coefficient(double ms) { return Math.exp(-1000/(rate*ms)); }
    static double amp(double db) { return Math.pow(10,db/20); }
    private static double clamp(double x,double min,double max) { return Math.max(min,Math.min(max,x)); }

    float[] dynamicGains() { return dynamicDb.clone(); }

    void process(float[] pcm, int count, Settings active) {
        final float[] p=active.values;
        if (active!=settings) {
            settings=active;
            attack=coefficient(p[6]); release=coefficient(p[7]); trim=amp(p[8]);
            for (Lane lane:lanes) {
                lane.presence.tune(0,3200,5*p[2],rate);
                for (int i=0;i<6;i++) {
                    lane.detector[i].tune(3,p[10+i*6],0,rate);
                    lane.dynamicBand[i].tune(3,p[10+i*6],0,rate);
                }
            }
            counter=0;
        }
        for (int frame=0;frame<count;frame+=lanes.length) {
            double peak=0;
            double inputPower=0;
            for (int c=0;c<lanes.length;c++) {
                double sample=pcm[frame+c];
                peak=Math.max(peak,Math.abs(sample));
                inputPower+=sample*sample;
            }
            fast+=(peak-fast)*(peak>fast ? .012 : .002);
            slow+=(fast-slow)*.0002;
            floor+=(fast-floor)*(fast<floor ? .004 : .000008);
            double gate=clamp((fast-(floor*1.5+0.001))/(floor*2+0.008),0,1);
            double decay=clamp((slow-fast)/(slow+0.002),0,1);
            double setup=(1-p[0]*.92*(1-gate))*(1-p[1]*.83*decay);
            levelPower+=(inputPower/lanes.length*setup*setup-levelPower)*rmsStep;
            if (counter++%64==0) {
                double rmsDb=10*Math.log10(levelPower+1e-12);
                double voiced=clamp((rmsDb+53)/13,0,1);
                double correction=clamp((-22-rmsDb)*.65,-9,9);
                if (correction>0) correction*=voiced;
                levelTarget=amp(correction*p[3]);
                for (int b=0;b<6;b++) {
                    int k=10+b*6;
                    double db=10*Math.log10(bandPower[b]+1e-12);
                    double dyn=p[k+4]*clamp((db-p[k+3])/18,0,1);
                    dynamicDb[b]=(float)dyn;
                    dynamicCut[b]=amp(dyn)-1;
                    for (Lane lane:lanes) lane.eq[b].tune((int)p[k+5],p[k],p[k+1]+dyn,rate);
                }
            }
            level+=(levelTarget-level)*(levelTarget<level?turnDownStep:turnUpStep);
            for (int i=0;i<6;i++) {
                double power=0;
                for (int c=0;c<lanes.length;c++) {
                    double signal=lanes[c].detector[i].tick(pcm[frame+c]*setup);
                    power+=signal*signal;
                }
                bandPower[i]+=(power/lanes.length-bandPower[i])*.002;
            }
            peak=0;
            for (int c=0;c<lanes.length;c++) {
                Lane lane=lanes[c];
                double x=pcm[frame+c];
                x=lane.presence.tick((x+(lane.low.tick(x)-x)*p[0])*setup)*(p[3]==0?1:level);
                double wet=0;
                for (int i=0;i<6;i++) {
                    int k=10+i*6;
                    double dry=x;
                    x=lane.eq[i].tick(x);
                    if (p[k+5]!=0) {
                        double blend=clamp((p[k+1]+18)/36,0,1);
                        // Vertical dragging sets the wet mix in pass-filter modes.
                        x=dry+(x-dry)*blend;
                        x+=lane.dynamicBand[i].tick(dry)*dynamicCut[i];
                    }
                    int slot=lane.cursor[i];
                    float delayed=lane.echo[i][slot];
                    double isolated=lane.detector[i].y1;
                    lane.echo[i][slot]=(float)(isolated+delayed*.48);
                    lane.cursor[i]=(slot+1)%lane.echo[i].length;
                    wet+=delayed*p[k+2]*.30;
                }
                pcm[frame+c]=(float)(x+wet);
                peak=Math.max(peak,Math.abs(x+wet));
            }
            double above=20*Math.log10(peak+1e-9)-p[5];
            double knee=clamp(above+4,0,8);
            double over=Math.max(0,above-4)+knee*knee/16;
            double gain=amp(-over*(.48+p[4]*.34));
            double time=gain<comp ? attack : release;
            comp=time*comp+(1-time)*gain;
            double detail=1+p[4]*1.15*gate;
            double drive=1+p[9]*4;
            peak=0;
            for (int c=0;c<lanes.length;c++) {
                double x=pcm[frame+c]*comp*detail;
                if (p[9]>0) {
                    double shaped=Math.tanh(x*drive)/drive;
                    x+=(shaped-x)*p[9];
                }
                x*=trim;
                pcm[frame+c]=(float)x;
                peak=Math.max(peak,Math.abs(x));
            }
            limiter=Math.min(peak>.98 ? .98/peak : 1,limiter+(1-limiter)*.00025);
            for (int c=0;c<lanes.length;c++) pcm[frame+c]*=limiter;
        }
    }
}
