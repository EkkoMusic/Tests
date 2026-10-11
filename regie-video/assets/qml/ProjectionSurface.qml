// Surface de projection accélérée (Qt Quick, rendu GPU).
// Vidéo, image fixe et noir sont trois couches d'une même scène : changer de
// couche est une mise à jour atomique de la scène, sans fenêtre native
// supplémentaire. Les images vidéo sont relayées par l'application (aucune
// conversion, aucune copie) ; l'image vide émise par Qt en fin de média est
// filtrée, donc la dernière image reste à l'écran jusqu'à la bascule.
import QtQuick
import QtMultimedia

Rectangle {
    id: root
    color: "black"

    // « black », « video » ou « still »
    property string mode: "black"
    property bool blackout: false
    // 0 = adapter (sans recadrage), 1 = remplir (recadrage), 2 = taille native
    property int fitMode: 0
    property size nativeSize: Qt.size(0, 0)       // vidéo : taille native en pixels logiques
    property size stillNativeSize: Qt.size(0, 0)  // image : taille native en pixels logiques
    property string stillSource: ""
    property string stillPreload: ""

    Item {
        id: stage
        anchors.fill: parent
        clip: true

        // Préchargement : l'image suivante est rendue sous le fond noir pour que
        // sa texture soit déjà sur le GPU au moment de l'afficher.
        Image {
            anchors.fill: parent
            source: root.stillPreload
            asynchronous: false
            cache: false
            fillMode: root.fitMode === 1 ? Image.PreserveAspectCrop : Image.PreserveAspectFit
            smooth: true
            z: 0
        }
        Rectangle { anchors.fill: parent; color: "black"; z: 1 }

        VideoOutput {
            id: video
            objectName: "video"
            z: 2
            visible: root.mode === "video"
            anchors.centerIn: parent
            width: root.fitMode === 2 && root.nativeSize.width > 0 ? root.nativeSize.width : parent.width
            height: root.fitMode === 2 && root.nativeSize.height > 0 ? root.nativeSize.height : parent.height
            fillMode: root.fitMode === 1 ? VideoOutput.PreserveAspectCrop : VideoOutput.PreserveAspectFit
        }

        Image {
            id: still
            objectName: "still"
            z: 3
            visible: root.mode === "still"
            anchors.centerIn: parent
            width: root.fitMode === 2 && root.stillNativeSize.width > 0 ? root.stillNativeSize.width : parent.width
            height: root.fitMode === 2 && root.stillNativeSize.height > 0 ? root.stillNativeSize.height : parent.height
            source: root.stillSource
            asynchronous: false
            cache: false
            fillMode: root.fitMode === 1 ? Image.PreserveAspectCrop : Image.PreserveAspectFit
            smooth: true
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "black"
        visible: root.blackout || root.mode === "black"
        z: 10
    }
}
