// Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import 'Track.js' as Track
Item {
    id: root
    width: 380
    height: 650
    property int revision: 0
    function position() { return Math.max(0, producer.position - (filter.in - producer.in)); }
    function coordinate(corner, axis) {
        var r=revision;
        return ((filter.getDouble(String(corner*2+axis), position())*3-1)*(axis ? profile.height-1 : profile.width-1)).toFixed(1);
    }
    function setCoordinate(corner, axis, text) {
        var n=Number(text), dim=axis ? profile.height-1 : profile.width-1;
        if (!isFinite(n) || n < -dim || n > 2*dim) { status.text='坐标超出范围。'; return; }
        filter.set(String(corner*2+axis), (n/dim+1)/3, position());
        revision++;
    }
    Component.onCompleted: {
        if (filter.isNew) {
            var defaults=[1/3,1/3,2/3,1/3,2/3,2/3,1/3,2/3,1];
            for (var i=0;i<9;i++) filter.set(String(i), defaults[i]);
        }
        revision++;
    }
    Connections { target: producer; function onPositionChanged(){root.revision++;} }
    Connections { target: filter; function onChanged(){root.revision++;} }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 9
        Label { text: '表面贴字 · 透视跟踪'; font.bold: true; font.pixelSize: 18 }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: '请把滤镜放在透明字幕轨道上。先在随包助手选四角并自动跟踪，再打开生成的 Shotcut 工程。切勿对原视频加此滤镜。'
        }
        Label { text: '当前帧四角（像素，可直接改值）'; font.bold: true }
        Repeater {
            model: ['左上','右上','右下','左下']
            delegate: RowLayout {
                required property int index
                required property string modelData
                Label { text: modelData; Layout.preferredWidth: 45 }
                Label { text: 'X' }
                TextField { Layout.preferredWidth: 100; text: root.coordinate(index,0); selectByMouse: true; onEditingFinished: root.setCoordinate(index,0,text) }
                Label { text: 'Y' }
                TextField { Layout.preferredWidth: 100; text: root.coordinate(index,1); selectByMouse: true; onEditingFinished: root.setCoordinate(index,1,text) }
            }
        }
        Label { text: '重新导入跟踪数据（助手内点“复制跟踪数据”）'; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 120
            TextArea { id: data; placeholderText: '在这里粘贴 tracking.json 全文'; selectByMouse: true; wrapMode: TextEdit.Wrap }
        }
        Button {
            text: '导入全部透视关键帧'
            enabled: data.text.length>0
            onClicked: {
                try {
                    var values=Track.build(data.text, profile.width, profile.height, profile.fps, filter.duration);
                    filter.startUndoParameterCommand('导入平面透视跟踪');
                    try {
                        filter.blockSignals=true;
                        for(var i=0;i<9;i++) {filter.resetProperty(String(i)); filter.set(String(i),values[i]);}
                    } finally {filter.blockSignals=false;filter.changed();filter.endUndoCommand();}
                    status.text='导入成功。参考帧前和丢失帧将隐藏字幕。';
                    root.revision++;
                } catch(e) {status.text=String(e);}
            }
        }
        Label { id: status; Layout.fillWidth: true; wrapMode: Text.WordWrap; text: '文字内容需在助手中修改并重新生成。四角关键帧可在此或关键帧面板编辑。' }
        Item { Layout.fillHeight: true }
    }
}
