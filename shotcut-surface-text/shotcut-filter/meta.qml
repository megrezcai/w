// Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.shotcut.qml
Metadata {
    type: Metadata.Filter
    objectName: 'surface_text'
    name: '表面贴字 · 透视跟踪'
    mlt_service: 'frei0r.surfacepin'
    qml: 'ui.qml'
    keywords: 'perspective planar surface text tracking 透视 平面 字幕 跟踪 #rgba'
    keyframes {
        allowAnimateIn: false
        allowAnimateOut: false
        parameters: [
            Parameter { name: '左上 X'; property: '0'; isCurve: true; minimum: 0; maximum: 1 },
            Parameter { name: '左上 Y'; property: '1'; isCurve: true; minimum: 0; maximum: 1 },
            Parameter { name: '右上 X'; property: '2'; isCurve: true; minimum: 0; maximum: 1 },
            Parameter { name: '右上 Y'; property: '3'; isCurve: true; minimum: 0; maximum: 1 },
            Parameter { name: '右下 X'; property: '4'; isCurve: true; minimum: 0; maximum: 1 },
            Parameter { name: '右下 Y'; property: '5'; isCurve: true; minimum: 0; maximum: 1 },
            Parameter { name: '左下 X'; property: '6'; isCurve: true; minimum: 0; maximum: 1 },
            Parameter { name: '左下 Y'; property: '7'; isCurve: true; minimum: 0; maximum: 1 },
            Parameter { name: '可见度'; property: '8'; isCurve: true; minimum: 0; maximum: 1 }
        ]
    }
}
