# -*- coding: utf-8 -*-
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsFeature,
    QgsGeometry,
    QgsField,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform
)
from PyQt5.QtCore import QVariant
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'map_updater_dialog_base.ui'))

class MapUpdaterDialog(QDialog, FORM_CLASS):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.setupUi(self)

        self.btnLoadOrthophoto.clicked.connect(self.load_orthophoto)
        self.btnLoadCadastral.clicked.connect(self.load_cadastral)
        self.btnLoadYoloResult.clicked.connect(self.load_yolo_results)
        self.btnClassifyNewBuildings.clicked.connect(self.classify_new_buildings)
        self.btnProcessSAMResult.clicked.connect(self.process_sam_results)
        self.btnUpdateCadastralMap.clicked.connect(self.update_cadastral_map)

    def load_orthophoto(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "정사영상 불러오기", "", "Raster files (*.tif *.tiff *.jpg *.jp2);;All files (*)")
        if file_path:
            layer = QgsRasterLayer(file_path, os.path.basename(file_path))
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
            else:
                QMessageBox.warning(self, "오류", "정사영상이 유효하지 않습니다.")

    def load_cadastral(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "수치지도 불러오기", "", "Shapefiles (*.shp);;All files (*)")
        if file_path:
            layer = QgsVectorLayer(file_path, os.path.basename(file_path), "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
            else:
                QMessageBox.warning(self, "오류", "수치지도가 유효하지 않습니다.")

    def load_yolo_results(self):
        files, _ = QFileDialog.getOpenFileNames(self, "건물 탐지 결과 GeoJSON 선택", "", "GeoJSON files (*.geojson);;All files (*)")
        if not files:
            return

        loaded_count = 0
        failed_files = []
        for file_path in files:
            layer = QgsVectorLayer(file_path, os.path.basename(file_path), "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                loaded_count += 1
            else:
                failed_files.append(os.path.basename(file_path))

        if loaded_count > 0:
            QMessageBox.information(self, "불러오기 완료", f"{loaded_count}개의 GeoJSON 레이어가 추가되었습니다.")
        if failed_files:
            QMessageBox.warning(self, "불러오기 실패", f"다음 파일을 불러오지 못했습니다:\n" + "\n".join(failed_files))

    def classify_new_buildings(self):
        IOU_THRESH = 0.3
        layers = [layer for layer in QgsProject.instance().mapLayers().values() if layer.name().endswith(".geojson") or layer.source().endswith(".geojson")]
        if len(layers) < 2:
            QMessageBox.warning(self, "레이어 부족", "GeoJSON 건물 탐지 레이어 2개가 필요합니다.")
            return

        det_layer = layers[-1]
        cad_layer = layers[-2]

        det_features = list(det_layer.getFeatures())
        cad_features = list(cad_layer.getFeatures())

        def compute_iou(geom1, geom2):
            if not geom1.intersects(geom2):
                return 0.0
            inter_area = geom1.intersection(geom2).area()
            union_area = geom1.area() + geom2.area() - inter_area
            return inter_area / union_area if union_area else 0.0

        new_features = []
        for feat in det_features:
            geom = feat.geometry()
            max_iou = max((compute_iou(geom, cad_feat.geometry()) for cad_feat in cad_features), default=0.0)
            if max_iou < IOU_THRESH:
                new_features.append(feat)

        if not new_features:
            QMessageBox.information(self, "결과 없음", "IOU < 0.3 조건을 만족하는 신규 건물이 없습니다.")
            return

        crs = det_layer.crs().authid()
        new_layer = QgsVectorLayer(f"Polygon?crs={crs}", "신규_건물", "memory")
        new_layer.startEditing()
        new_layer.dataProvider().addAttributes([QgsField("id", QVariant.Int)])
        new_layer.updateFields()

        for idx, feat in enumerate(new_features):
            new_feat = QgsFeature(new_layer.fields())
            new_feat.setGeometry(feat.geometry())
            new_feat.setAttribute("id", idx + 1)
            new_layer.addFeature(new_feat)

        new_layer.commitChanges()
        QgsProject.instance().addMapLayer(new_layer)
        QMessageBox.information(self, "완료", f"신규 건물 {len(new_features)}개 레이어로 분류 완료되었습니다.")

    def process_sam_results(self):
        files, _ = QFileDialog.getOpenFileNames(self, "SAM 결과 SHP 선택", "", "Shapefiles (*.shp);;All files (*)")
        if not files:
            return

        target_crs = QgsCoordinateReferenceSystem("EPSG:5186")
        merged_features = []
        merged_fields = None

        for path in files:
            layer = QgsVectorLayer(path, os.path.basename(path), "ogr")
            if not layer.isValid():
                QMessageBox.warning(self, "오류", f"{path} 레이어가 유효하지 않습니다.")
                continue

            transform = None
            if layer.crs() != target_crs:
                transform = QgsCoordinateTransform(layer.crs(), target_crs, QgsProject.instance())

            if merged_fields is None:
                merged_fields = layer.fields()

            for feat in layer.getFeatures():
                geom = feat.geometry()
                if transform:
                    geom.transform(transform)
                new_feat = QgsFeature()
                new_feat.setGeometry(geom)
                new_feat.setFields(merged_fields)
                new_feat.setAttributes(feat.attributes())
                merged_features.append(new_feat)

        if not merged_features:
            QMessageBox.information(self, "결과 없음", "유효한 피처가 없습니다.")
            return

        merged_layer = QgsVectorLayer("Polygon?crs=EPSG:5186", "SAM_병합결과", "memory")
        merged_layer.dataProvider().addAttributes(merged_fields)
        merged_layer.updateFields()
        merged_layer.dataProvider().addFeatures(merged_features)
        QgsProject.instance().addMapLayer(merged_layer)

        QMessageBox.information(self, "완료", f"{len(files)}개 SHP 파일을 병합한 결과 레이어가 생성되었습니다.")

    def update_cadastral_map(self):
        layers = QgsProject.instance().mapLayers().values()
        new_layer = next((l for l in layers if l.name() == "SAM_병합결과" or "신규" in l.name()), None)
        old_layer = next((l for l in layers if "수치지도" in l.name() or "N3A_" in l.name()), None)

        if not new_layer or not old_layer:
            QMessageBox.warning(self, "레이어 없음", "기존 수치지도 또는 신규 건물 레이어가 없습니다.")
            return

        old_fields = old_layer.fields()
        field_names = [f.name() for f in old_fields]
        if "id" not in field_names:
            id_field = QgsField("id", QVariant.Int)
            old_fields.append(id_field)
            field_names.append("id")

        merged_layer = QgsVectorLayer(f"Polygon?crs={old_layer.crs().authid()}", "갱신된_수치지도", "memory")
        provider = merged_layer.dataProvider()
        provider.addAttributes(old_fields)
        merged_layer.updateFields()

        max_id = 0
        for idx, feat in enumerate(old_layer.getFeatures()):
            attrs = feat.attributes()
            geom = feat.geometry()
            new_feat = QgsFeature(merged_layer.fields())
            new_feat.setGeometry(geom)
            if len(attrs) < len(field_names):
                attrs += [None] * (len(field_names) - len(attrs))
            if attrs[field_names.index("id")] is None:
                attrs[field_names.index("id")] = idx + 1
            max_id = max(max_id, attrs[field_names.index("id")])
            new_feat.setAttributes(attrs)
            provider.addFeature(new_feat)

        for i, feat in enumerate(new_layer.getFeatures()):
            new_feat = QgsFeature(merged_layer.fields())
            new_feat.setGeometry(feat.geometry())
            attrs = [None] * len(field_names)
            attrs[field_names.index("id")] = max_id + i + 1
            new_feat.setAttributes(attrs)
            provider.addFeature(new_feat)

        merged_layer.commitChanges()
        QgsProject.instance().addMapLayer(merged_layer)
        QMessageBox.information(self, "완료", "✅ 수치지도가 자동으로 갱신되었습니다.")
