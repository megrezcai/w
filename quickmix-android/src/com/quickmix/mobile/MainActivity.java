package com.quickmix.mobile;

import android.app.*;
import android.content.*;
import android.database.Cursor;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.media.*;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.Locale;
import java.util.concurrent.*;

public final class MainActivity extends Activity {
    static final int BG=0xff10191e, CARD=0xff1a282f, LINE=0xff34474e;
    static final int INK=0xffedf5ed, MUTED=0xffa7bab9, LIME=0xffb9f880;
    static final int IMPORT=10, EXPORT=11;
    final ExecutorService files=Executors.newSingleThreadExecutor();
    volatile Mixer.Settings live=new Mixer.Settings();
    Mixer.Settings edit=live.copy();
    Mixer.Settings exportSettings;
    AudioFile exportAudio, audio;
    static final class EqFrame {
        final Mixer.Settings settings;
        final float[] bins, gains;
        final boolean original;
        EqFrame(Mixer.Settings settings,float[] bins,float[] gains,boolean original) {
            this.settings=settings; this.bins=bins; this.gains=gains; this.original=original;
        }
    }
    volatile EqFrame eqFrame;
    volatile boolean monitorEq;
    volatile float meter;
    volatile boolean dry;
    volatile int position;
    boolean busy, seeking;
    int page, effect, band;
    String name="";
    LinearLayout root, body;
    TextView trackName, time, level;
    Button play;
    SeekBar seek;
    EqGraph graph;
    LinearLayout bandControls;
    Playback playback;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        setVolumeControlStream(AudioManager.STREAM_MUSIC);
        if (state!=null) {
            float[] v=state.getFloatArray("settings");
            if (v!=null && v.length==edit.values.length) {
                System.arraycopy(v,0,edit.values,0,v.length);
                publish();
            }
        }
        build();
        root.post(tick);
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        state.putFloatArray("settings",edit.values.clone());
    }
    @Override protected void onStop() { stopPlayback(); super.onStop(); }
    @Override protected void onDestroy() {
        root.removeCallbacks(tick);
        files.shutdownNow();
        super.onDestroy();
    }

    int dp(float value) { return Math.round(value*getResources().getDisplayMetrics().density); }
    String fmt(String format,Object... args) { return String.format(Locale.ROOT,format,args); }
    GradientDrawable fill(int color,int radius) {
        GradientDrawable b=new GradientDrawable();
        b.setColor(color);
        b.setCornerRadius(dp(radius));
        return b;
    }
    LinearLayout column() {
        LinearLayout layout=new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }
    LinearLayout row() { return new LinearLayout(this); }
    TextView label(String title,int size,int color) {
        TextView label=new TextView(this);
        label.setText(title);
        label.setTextSize(size);
        label.setTextColor(color);
        return label;
    }
    TextView heading(String title,int size) {
        TextView text=label(title,size,INK);
        text.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        return text;
    }
    void gap(LinearLayout parent,int height) { parent.addView(new View(this),1,dp(height)); }
    Button action(String title,boolean active,Runnable run) {
        Button button=new Button(this);
        button.setAllCaps(false);
        button.setText(title);
        button.setTextSize(13);
        button.setTextColor(active ? BG : INK);
        button.setBackgroundTintList(null);
        button.setBackground(fill(active ? LIME : CARD,12));
        button.setMinHeight(dp(44));
        button.setMinimumHeight(dp(44));
        button.setMinWidth(0);
        button.setPadding(dp(5),0,dp(5),0);
        button.setOnClickListener(v -> run.run());
        return button;
    }
    void shareRow(LinearLayout container,View... items) {
        LinearLayout line=row();
        for (int i=0;i<items.length;i++) {
            LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-2,1);
            if (i>0) p.leftMargin=dp(6);
            line.addView(items[i],p);
        }
        container.addView(line,new LinearLayout.LayoutParams(-1,-2));
    }
    void publish() { live=edit.copy(); if (graph!=null) graph.invalidate(); }
    void build() {
        root=column();
        root.setBackgroundColor(BG);
        root.setPadding(dp(16),dp(12),dp(16),dp(12));
        setContentView(root);
        root.addView(heading("声场  QuickMix",26));
        gap(root,10);
        shareRow(root,action("主界面",page==0,() -> show(0)),
            action("预制",page==1,() -> show(1)),action("混音",page==2,() -> show(2)));
        gap(root,8);
        ScrollView scroll=new ScrollView(this);
        scroll.setFillViewport(true);
        body=column();
        scroll.addView(body);
        root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout transport=column();
        transport.setPadding(dp(10),dp(6),dp(10),dp(8));
        transport.setBackground(fill(CARD,14));
        LinearLayout strip=row();
        time=label("",12,MUTED);
        strip.addView(time,new LinearLayout.LayoutParams(0,-2,1));
        level=label("",12,LIME);
        strip.addView(level);
        transport.addView(strip);
        seek=new SeekBar(this);
        seek.setMax(1000);
        seek.setContentDescription("播放进度");
        seek.setProgressTintList(android.content.res.ColorStateList.valueOf(LIME));
        seek.setThumbTintList(android.content.res.ColorStateList.valueOf(LIME));
        seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            public void onStartTrackingTouch(SeekBar bar) { seeking=true; }
            public void onStopTrackingTouch(SeekBar bar) {
                seeking=false;
                if (audio==null) return;
                boolean resume=playback!=null;
                stopPlayback();
                position=(int)(audio.frames()*bar.getProgress()/1000L);
                if (resume && position<audio.frames()) startPlayback();
            }
            public void onProgressChanged(SeekBar bar,int progress,boolean user) {
                if (user && audio!=null) time.setText(clock((int)(audio.frames()*progress/1000L),audio.rate)
                    +" / "+clock(audio.frames(),audio.rate));
            }
        });
        transport.addView(seek,new LinearLayout.LayoutParams(-1,dp(29)));
        play=action("试听",true,() -> {
            if (playback==null) startPlayback(); else stopPlayback();
        });
        Button bypass=action("A/B · 效果",false,() -> {
            dry=!dry;
            if (graph!=null) graph.invalidate();
            ((Button)transport.findViewById(57)).setText(dry?"A/B · 原声":"A/B · 效果");
        });
        bypass.setId(57);
        shareRow(transport,play,bypass);
        root.addView(transport);
        show(page);
    }
    void show(int next) {
        page=next;
        LinearLayout navigation=(LinearLayout)root.getChildAt(2);
        for (int i=0;i<3;i++) {
            Button button=(Button)navigation.getChildAt(i);
            button.setTextColor(i==page?BG:INK);
            button.setBackground(fill(i==page?LIME:CARD,12));
        }
        body.removeAllViews();
        graph=null;
        monitorEq=page==2 && effect==0;
        eqFrame=null;
        trackName=null;
        if (page==0) home();
        else if (page==1) prep();
        else mix();
        ((ScrollView)body.getParent()).scrollTo(0,0);
        refresh();
    }
    void home() {
        gap(body,16);
        body.addView(heading("当前作品",24));
        gap(body,12);
        LinearLayout card=column();
        card.setPadding(dp(16),dp(18),dp(16),dp(16));
        card.setBackground(fill(CARD,16));
        trackName=heading("",19);
        card.addView(trackName);
        gap(card,6);
        card.addView(label("单声道或立体声 · 本机离线处理",13,MUTED));
        gap(card,16);
        card.addView(action("导入音频",true,this::chooseAudio),-1,dp(46));
        body.addView(card,-1,-2);
        gap(body,14);
        body.addView(action("导出 WAV",true,this::chooseExport),-1,dp(48));
        gap(body,14);
        body.addView(heading("参数预设",18));
        gap(body,8);
        shareRow(body,action("保存参数",false,this::savePreset),
            action("读取参数",false,this::loadPreset));
        gap(body,8);
        body.addView(label("可将同一套参数用于下一段录音。",13,MUTED));
    }
    void prep() {
        gap(body,12);
        body.addView(heading("人声预制",22));
        gap(body,6);
        body.addView(label("减少底噪和房间尾音，调整清晰度。智能响度可平衡段落之间的音量。",13,MUTED));
        gap(body,12);
        shareRow(body,knob("降噪",0,0,1,"%"),knob("去混响",1,0,1,"%"));
        shareRow(body,knob("声线清晰",2,0,1,"%"),knob("智能响度",3,0,1,"%"));
    }
    void mix() {
        gap(body,8);
        shareRow(body,action("EQ",effect==0,() -> setEffect(0)),
            action("压缩器",effect==1,() -> setEffect(1)),action("染色",effect==2,() -> setEffect(2)));
        gap(body,10);
        if (effect==0) {
            LinearLayout panel=row();
            graph=new EqGraph();
            LinearLayout.LayoutParams plot=new LinearLayout.LayoutParams(0,dp(258),1);
            plot.rightMargin=dp(8);
            panel.addView(graph,plot);
            bandControls=column();
            panel.addView(bandControls,new LinearLayout.LayoutParams(dp(108),-2));
            body.addView(panel,-1,-2);
            renderBand();
        } else if (effect==1) {
            body.addView(label("软拐点压缩 · 双声道联动",13,MUTED));
            gap(body,12);
            shareRow(body,knob("细节提升",4,0,1,"%"),knob("压缩阈值",5,-55,0,"dBFS"));
            shareRow(body,knob("Attack",6,1,100,"ms"),knob("Release",7,20,600,"ms"));
        } else {
            body.addView(label("柔和饱和 · 主输出限峰",13,MUTED));
            gap(body,12);
            shareRow(body,knob("全局响度",8,-18,12,"dB"),knob("暖色饱和",9,0,1,"%"));
        }
    }
    void setEffect(int next) { effect=next; show(2); }
    void renderBand() {
        bandControls.removeAllViews();
        int k=10+6*band;
        TextView bandLabel=heading(fmt("%d · %.0f Hz",band+1,edit.values[k]),13);
        bandLabel.setId(58);
        bandControls.addView(bandLabel);
        String[] modes={"峰值","高通","低通"};
        gap(bandControls,4);
        for (int i=0;i<modes.length;i++) {
            int mode=i;
            bandControls.addView(action(modes[i],edit.values[k+5]==i,() -> {
                edit.values[k+5]=mode;
                publish();
                renderBand();
            }),-1,dp(44));
            gap(bandControls,3);
        }
        bandControls.addView(knob("频段混响",k+2,0,1,"%"),-1,dp(86));
        bandControls.addView(knob("动态阈值",k+3,-72,0,"dBFS"),-1,dp(86));
        bandControls.addView(knob("动态幅度",k+4,-18,18,"dB"),-1,dp(86));
    }
    Knob knob(String title,int index,float min,float max,String unit) {
        return new Knob(title,index,min,max,unit);
    }

    final class Knob extends View {
        final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);
        final String title,unit;
        final int index;
        final float min,max;
        float startX,startY,initial;
        Knob(String title,int index,float min,float max,String unit) {
            super(MainActivity.this);
            this.title=title; this.index=index; this.min=min; this.max=max; this.unit=unit;
            setFocusable(true);
            describe();
        }
        String value() {
            float v=edit.values[index];
            return unit.equals("%") ? fmt("%.0f%%",v*100) : fmt("%.0f %s",v,unit);
        }
        void describe() { setContentDescription(title+" "+value()); }
        @Override protected void onMeasure(int w,int h) {
            setMeasuredDimension(MeasureSpec.getSize(w),resolveSize(dp(139),h));
        }
        @Override protected void onDraw(Canvas c) {
            float cx=getWidth()/2f, cy=getHeight()*.40f;
            float r=Math.min(cx-dp(8),dp(getHeight()>dp(105)?29:18));
            if (r<=0) return;
            p.setStyle(Paint.Style.FILL);
            p.setColor(CARD);
            c.drawRoundRect(0,dp(2),getWidth(),getHeight()-dp(3),dp(12),dp(12),p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(dp(4));
            p.setStrokeCap(Paint.Cap.ROUND);
            p.setColor(LINE);
            c.drawArc(cx-r,cy-r,cx+r,cy+r,135,270,false,p);
            p.setColor(LIME);
            c.drawArc(cx-r,cy-r,cx+r,cy+r,135,270*(edit.values[index]-min)/(max-min),false,p);
            p.setStyle(Paint.Style.FILL);
            p.setTextAlign(Paint.Align.CENTER);
            p.setTextSize(dp(11));
            c.drawText(value(),cx,cy+dp(4),p);
            p.setColor(INK);
            p.setTextSize(dp(12));
            c.drawText(title,cx,getHeight()-dp(10),p);
        }
        @Override public boolean onTouchEvent(android.view.MotionEvent e) {
            switch(e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    getParent().requestDisallowInterceptTouchEvent(true);
                    startX=e.getX(); startY=e.getY(); initial=edit.values[index];
                    return true;
                case MotionEvent.ACTION_MOVE:
                    change(initial+((startY-e.getY())+(e.getX()-startX)*.45f)/dp(126)*(max-min));
                    return true;
                case MotionEvent.ACTION_UP:
                    performClick();
                    return true;
                case MotionEvent.ACTION_CANCEL: return true;
                default: return true;
            }
        }
        @Override public boolean performClick() { super.performClick(); return true; }
        void change(float value) {
            edit.values[index]=Math.max(min,Math.min(max,value));
            describe();
            publish();
            invalidate();
        }
        @Override public boolean onKeyDown(int key,android.view.KeyEvent event) {
            if (key==KeyEvent.KEYCODE_DPAD_LEFT || key==KeyEvent.KEYCODE_DPAD_RIGHT) {
                change(edit.values[index]+(key==KeyEvent.KEYCODE_DPAD_LEFT?-1:1)*(max-min)/30);
                return true;
            }
            return super.onKeyDown(key,event);
        }
        @Override public void onInitializeAccessibilityNodeInfo(android.view.accessibility.AccessibilityNodeInfo info) {
            super.onInitializeAccessibilityNodeInfo(info);
            info.setClassName(SeekBar.class.getName());
            info.setRangeInfo(android.view.accessibility.AccessibilityNodeInfo.RangeInfo.obtain(1,min,max,edit.values[index]));
            info.addAction(android.view.accessibility.AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_PROGRESS);
        }
        @Override public boolean performAccessibilityAction(int action,Bundle args) {
            if (action==android.view.accessibility.AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_PROGRESS.getId() && args!=null) {
                change(args.getFloat(android.view.accessibility.AccessibilityNodeInfo.ACTION_ARGUMENT_PROGRESS_VALUE));
                return true;
            }
            return super.performAccessibilityAction(action,args);
        }
    }

    final class EqGraph extends View {
        final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);
        final Mixer.Filter[] filters=new Mixer.Filter[6], bandPass=new Mixer.Filter[6];
        final double[] response=new double[2], bandResponse=new double[2];
        final double[] bandMix=new double[6], bandScale=new double[6];
        final Path curve=new Path();
        final DashPathEffect dash=new DashPathEffect(new float[]{dp(4),dp(3)},0);
        int drag=-1;
        EqGraph() {
            super(MainActivity.this);
            for (int i=0;i<6;i++) {
                filters[i]=new Mixer.Filter();
                bandPass[i]=new Mixer.Filter();
            }
            setContentDescription("六段均衡器。拖动控制点调整频率和增益。");
        }
        float left() { return dp(19); }
        float right() { return getWidth()-dp(14); }
        float top() { return dp(28); }
        float bottom() { return getHeight()-dp(28); }
        float x(double hz) { return left()+(right()-left())*(float)(Math.log(hz/20)/Math.log(1000)); }
        float y(float value) { return top()+(bottom()-top())*(18-value)/36; }
        double hz(float x) { return 20*Math.pow(1000,(x-left())/(right()-left())); }
        void drawLine(Canvas c,float x1,float y1,float x2,float y2,int color) {
            p.setColor(color);
            p.setStrokeWidth(dp(1));
            c.drawLine(x1,y1,x2,y2,p);
        }
        @Override protected void onDraw(Canvas c) {
            final float[] values=edit.values;
            final int rate=audio==null?48000:audio.rate;
            p.setColor(CARD);
            c.drawRoundRect(0,0,getWidth(),getHeight(),dp(15),dp(15),p);
            p.setTextSize(dp(10));
            for (int db=-18;db<=18;db+=6) drawLine(c,left(),y(db),right(),y(db),db==0?MUTED:LINE);
            for (int f:new int[]{50,200,1000,5000,15000}) {
                drawLine(c,x(f),top(),x(f),bottom(),LINE);
                p.setColor(MUTED);
                c.drawText(f>=1000?(f/1000)+"k":""+f,x(f)-dp(5),bottom()+dp(16),p);
            }
            p.setColor(MUTED);
            EqFrame frame=eqFrame;
            boolean liveCurve=frame!=null && frame.settings==live && !dry && !frame.original;
            c.drawText(dry?"原声频谱 · EQ 旁路":liveCurve?"动态 EQ · 虚线为设定":"EQ 设定曲线",
                left(),dp(17),p);
            if (frame!=null && frame.original==dry) {
                float[] bins=frame.bins;
                Path path=new Path();
                path.moveTo(left(),bottom());
                for (int i=0;i<bins.length;i++) {
                    float bx=left()+i*(right()-left())/(bins.length-1);
                    path.lineTo(bx,bottom()-bins[i]*(bottom()-top()));
                }
                path.lineTo(right(),bottom());
                path.close();
                p.setColor(0x644b9392);
                c.drawPath(path,p);
            }
            drawResponse(c,values,rate,null,liveCurve?MUTED:LIME,liveCurve);
            if (liveCurve) drawResponse(c,values,rate,frame.gains,LIME,false);
            p.setTextSize(dp(10));
            p.setColor(LIME);
            if (liveCurve) {
                p.setTextAlign(Paint.Align.RIGHT);
                c.drawText(fmt("%+.1f dB",frame.gains[band]),right(),getHeight()-dp(4),p);
                p.setTextAlign(Paint.Align.LEFT);
            }
            for (int i=0;i<6;i++) {
                int k=10+i*6;
                p.setColor(i==band?LIME:INK);
                c.drawCircle(x(values[k]),y(values[k+1]),dp(i==band?8:6),p);
                p.setColor(BG);
                p.setTextSize(dp(8));
                c.drawText(""+(i+1),x(values[k])-dp(2),y(values[k+1])+dp(3),p);
            }
        }
        void drawResponse(Canvas c,float[] values,int rate,float[] gains,int color,boolean dashed) {
            for (int b=0;b<6;b++) {
                int k=10+b*6, mode=(int)values[k+5];
                double change=gains==null?0:gains[b];
                filters[b].tune(mode,values[k],values[k+1]+change,rate);
                bandMix[b]=mode==0?1:(values[k+1]+18)/36;
                bandScale[b]=mode==0?0:Mixer.amp(change)-1;
                if (bandScale[b]!=0) bandPass[b].tune(3,values[k],0,rate);
            }
            curve.rewind();
            float stop=Math.min(right(),x(rate*.49));
            for (int i=0;i<=100;i++) {
                float px=left()+i*(stop-left())/100;
                double frequency=hz(px), magnitude=1;
                for (int b=0;b<6;b++) {
                    filters[b].response(frequency,rate,response);
                    double real=1+(response[0]-1)*bandMix[b], imag=response[1]*bandMix[b];
                    if (bandScale[b]!=0) {
                        bandPass[b].response(frequency,rate,bandResponse);
                        real+=bandScale[b]*bandResponse[0];
                        imag+=bandScale[b]*bandResponse[1];
                    }
                    magnitude*=real*real+imag*imag;
                }
                float py=y((float)Math.max(-18,Math.min(18,10*Math.log10(magnitude+1e-12))));
                if (i==0) curve.moveTo(px,py); else curve.lineTo(px,py);
            }
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(dp(dashed?1:2));
            p.setPathEffect(dashed?dash:null);
            p.setColor(color);
            c.drawPath(curve,p);
            p.setPathEffect(null);
            p.setStyle(Paint.Style.FILL);
        }
        @Override public boolean onTouchEvent(MotionEvent e) {
            switch(e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    float best=Float.MAX_VALUE;
                    for (int i=0;i<6;i++) {
                        int k=10+i*6;
                        float dx=x(edit.values[k])-e.getX(), dy=y(edit.values[k+1])-e.getY();
                        float dist=dx*dx+dy*dy;
                        if (dist<best) { best=dist; drag=i; }
                    }
                    if (drag>=0) {
                        getParent().requestDisallowInterceptTouchEvent(true);
                        band=drag;
                        renderBand();
                        invalidate();
                    }
                    return true;
                case MotionEvent.ACTION_MOVE:
                    if (drag<0) return true;
                    int k=10+drag*6;
                    edit.values[k]=(float)hz(Math.max(left(),Math.min(right(),e.getX())));
                    edit.values[k+1]=18-36*(Math.max(top(),Math.min(bottom(),e.getY()))-top())/(bottom()-top());
                    ((TextView)bandControls.findViewById(58)).setText(fmt("%d · %.0f Hz",band+1,edit.values[k]));
                    publish();
                    return true;
                case MotionEvent.ACTION_UP:
                    drag=-1;
                    performClick();
                    return true;
                case MotionEvent.ACTION_CANCEL: drag=-1; return true;
                default: return true;
            }
        }
        @Override public boolean performClick() { super.performClick(); return true; }
    }

    void chooseAudio() {
        if (busy) return;
        Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("audio/*");
        startActivityForResult(pick,IMPORT);
    }
    void chooseExport() {
        if (busy) return;
        if (audio==null) { notice("请先导入音频"); return; }
        exportAudio=audio;
        exportSettings=live;
        Intent create=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
            .setType("audio/wav").putExtra(Intent.EXTRA_TITLE,"QuickMix-"+name.replaceFirst("\\.[^.]+$","")+".wav");
        startActivityForResult(create,EXPORT);
    }
    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if (result!=RESULT_OK || data==null || data.getData()==null) return;
        Uri uri=data.getData();
        if (request==IMPORT) {
            stopPlayback();
            busy=true;
            refresh();
            files.execute(() -> {
                try {
                    AudioFile next=AudioFile.read(this,uri);
                    String title="已导入音频";
                    try (Cursor cursor=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)) {
                        if (cursor!=null && cursor.moveToFirst() && cursor.getString(0)!=null) title=cursor.getString(0);
                    } catch (RuntimeException ignored) {}
                    String display=title;
                    runOnUiThread(() -> {
                        audio=next;
                        name=display;
                        position=0;
                        busy=false;
                        refresh();
                    });
                } catch (Exception e) { finishTask("导入失败 · "+reason(e)); }
            });
        } else if (request==EXPORT && exportAudio!=null && exportSettings!=null) {
            busy=true;
            refresh();
            AudioFile source=exportAudio;
            Mixer.Settings snapshot=exportSettings;
            exportAudio=null;
            exportSettings=null;
            files.execute(() -> {
                try (OutputStream destination=getContentResolver().openOutputStream(uri,"wt")) {
                    if (destination==null) throw new IOException("无法写入该位置");
                    source.write(destination,snapshot);
                } catch (Exception e) {
                    try { android.provider.DocumentsContract.deleteDocument(getContentResolver(),uri); }
                    catch (Exception ignored) {}
                    finishTask("导出失败 · "+reason(e));
                    return;
                }
                finishTask("WAV 已导出");
            });
        }
    }
    String reason(Exception e) { return e.getMessage()==null ? "请检查音频和文件权限" : e.getMessage(); }
    void finishTask(String message) {
        runOnUiThread(() -> { busy=false; refresh(); notice(message); });
    }
    void notice(String message) { Toast.makeText(this,message,Toast.LENGTH_SHORT).show(); }
    void savePreset() {
        org.json.JSONArray data=new org.json.JSONArray();
        try {
            for (float value:edit.values) data.put((double)value);
            getPreferences(MODE_PRIVATE).edit().putString("preset_v1",data.toString()).apply();
            notice("参数已保存");
        } catch (org.json.JSONException e) { notice("无法保存参数"); }
    }
    void loadPreset() {
        String data=getPreferences(MODE_PRIVATE).getString("preset_v1",null);
        if (data==null) { notice("尚未保存参数"); return; }
        try {
            org.json.JSONArray values=new org.json.JSONArray(data);
            Mixer.Settings next=new Mixer.Settings();
            if (values.length()!=next.values.length) throw new org.json.JSONException("预设版本不匹配");
            for (int i=0;i<values.length();i++) next.values[i]=(float)values.getDouble(i);
            edit=next;
            publish();
            show(page);
            notice("参数已读取");
        } catch (org.json.JSONException e) { notice("无法读取参数"); }
    }
    void startPlayback() {
        if (audio==null) { notice("请先导入音频"); return; }
        if (busy) return;
        if (position>=audio.frames()) position=0;
        playback=new Playback(audio,position);
        playback.start();
        refresh();
    }
    void stopPlayback() {
        Playback old=playback;
        playback=null;
        if (old!=null) old.cancelled=true;
        meter=0;
        eqFrame=null;
        if (graph!=null) graph.invalidate();
        if (play!=null) refresh();
    }
    String clock(int frames,int rate) {
        int seconds=frames/rate;
        return fmt("%02d:%02d",seconds/60,seconds%60);
    }
    void refresh() {
        if (trackName!=null) trackName.setText(busy?"正在处理…":audio==null?"尚未导入音频":name);
        play.setEnabled(audio!=null && !busy);
        play.setAlpha(play.isEnabled()?1f:.5f);
        play.setText(playback==null?"试听":"暂停");
        seek.setEnabled(audio!=null);
        if (!seeking) {
            time.setText(audio==null?"00:00 / 00:00":clock(position,audio.rate)+" / "+clock(audio.frames(),audio.rate));
            seek.setProgress(audio==null?0:(int)(1000L*position/audio.frames()));
        }
        level.setText(meter>0 ? fmt("%.0f dBFS",20*Math.log10(meter)) : "— dBFS");
    }
    final Runnable tick=new Runnable() {
        @Override public void run() {
            refresh();
            root.postDelayed(this,85);
        }
    };

    final class Playback extends Thread {
        final AudioFile file;
        final int startFrame;
        volatile boolean cancelled;
        Playback(AudioFile file,int startFrame) {
            super("QuickMix playback");
            this.file=file; this.startFrame=startFrame;
        }
        @Override public void run() {
            AudioTrack track=null;
            String failure=null;
            try {
                android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_AUDIO);
                int mask=file.channels==1?AudioFormat.CHANNEL_OUT_MONO:AudioFormat.CHANNEL_OUT_STEREO;
                int min=AudioTrack.getMinBufferSize(file.rate,mask,AudioFormat.ENCODING_PCM_16BIT);
                if (min<=0) throw new IOException("设备不支持此采样率");
                track=new AudioTrack.Builder().setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
                    .setAudioFormat(new AudioFormat.Builder().setSampleRate(file.rate).setChannelMask(mask)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
                    .setBufferSizeInBytes(Math.max(min,1024*file.channels*2)).build();
                if (cancelled) return;
                Mixer mixer=new Mixer(file.rate,file.channels);
                float[] buffer=new float[512*file.channels];
                short[] output=new short[buffer.length];
                int warmup=Math.max(0,startFrame-file.rate)*file.channels;
                for (int offset=warmup;offset<startFrame*file.channels && !cancelled;) {
                    int count=Math.min(buffer.length,startFrame*file.channels-offset);
                    file.block(offset,buffer);
                    mixer.process(buffer,count,live);
                    offset+=count;
                }
                track.play();
                int offset=startFrame*file.channels;
                int tail=0, untilFrame=0;
                Spectrum analyzer=new Spectrum(file.rate);
                for (int i=0;i<6;i++) if (live.values[12+i*6]>0) tail=file.rate*3/4*file.channels;
                if (dry) tail=0;
                while (!cancelled && offset<file.samples.length+tail) {
                    int count;
                    if (offset<file.samples.length) count=file.block(offset,buffer);
                    else {
                        count=Math.min(buffer.length,file.samples.length+tail-offset);
                        java.util.Arrays.fill(buffer,0,count,0f);
                    }
                    Mixer.Settings active=live;
                    mixer.process(buffer,count,active);
                    boolean original=dry;
                    float peak=0;
                    for (int i=0;i<count;i++) {
                        output[i]=original?(offset+i<file.samples.length?file.samples[offset+i]:0):AudioFile.quantize(buffer[i]);
                        peak=Math.max(peak,Math.abs(output[i]/32768f));
                    }
                    if (monitorEq) {
                        analyzer.add(output,count,file.channels,original);
                        untilFrame-=count/file.channels;
                        if (untilFrame<=0 && !cancelled) {
                            untilFrame+=file.rate/30;
                            EqFrame next=new EqFrame(active,analyzer.read(),mixer.dynamicGains(),original);
                            runOnUiThread(() -> {
                                if (playback!=this || !monitorEq) return;
                                eqFrame=next;
                                if (graph!=null) graph.postInvalidateOnAnimation();
                            });
                        }
                    } else {
                        analyzer.reset();
                        untilFrame=0;
                    }
                    int written=track.write(output,0,count,AudioTrack.WRITE_BLOCKING);
                    if (written!=count) throw new IOException("音频输出中断");
                    offset+=written;
                    if (!cancelled) {
                        meter=peak;
                        position=Math.min(file.frames(),startFrame+track.getPlaybackHeadPosition());
                    }
                }
                if (!cancelled) {
                    int remaining=offset/file.channels-startFrame-track.getPlaybackHeadPosition();
                    long timeout=android.os.SystemClock.elapsedRealtime()+Math.max(0,1000L*remaining/file.rate)+250;
                    while (!cancelled && track.getPlaybackHeadPosition()<offset/file.channels-startFrame
                        && android.os.SystemClock.elapsedRealtime()<timeout) Thread.sleep(10);
                    if (!cancelled) position=file.frames();
                }
            } catch (Exception e) { failure=reason(e); }
            finally {
                if (track!=null) track.release();
                String report=failure;
                runOnUiThread(() -> {
                    if (playback==this) {
                        stopPlayback();
                        if (report!=null) notice("试听失败 · "+report);
                    }
                });
            }
        }
    }
}
