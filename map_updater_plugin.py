import os
import sys

# 1) QGIS 앱 설치 경로 (본인 환경에 맞춰 수정)
QGIS_APPS = r"C:\Program Files\QGIS 3.40.4\apps"

# 2) QGIS 파이썬 바인딩 경로
PYTHON_SITE_PACKAGES = os.path.join(
    QGIS_APPS, "Python312", "Lib", "site-packages"
)
QGIS_PYTHON_MODULES = os.path.join(
    QGIS_APPS, "qgis-ltr", "python"
)

# 3) 모듈 검색 경로에 추가
sys.path.insert(0, PYTHON_SITE_PACKAGES)
sys.path.insert(0, QGIS_PYTHON_MODULES)

# 4) QGIS & PyQt5 바인딩 import
from qgis.core import QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt import QtCore

# 5) 헤드리스 QGIS 초기화
QGS_PREFIX = os.path.join(QGIS_APPS, "qgis-ltr")
qgs = QgsApplication([], False)
qgs.setPrefixPath(QGS_PREFIX, True)
qgs.initQgis()

def update_map_headless(orthophoto_path: str, cadastral_path: str) -> dict:
    # 진입 로그
    print(f"▶ update_map_headless called with:\n   orthophoto: {orthophoto_path}\n   cadastre : {cadastral_path}")

    # 1) 레이어 로드
    ortho = QgsRasterLayer(orthophoto_path, "orthophoto")
    cad   = QgsVectorLayer(cadastral_path, "cadastre", "ogr")
    if not ortho.isValid() or not cad.isValid():
        msg = "레이어 로드 실패"
        print(f"❌ {msg}")
        return {"status": "error", "message": msg}

    QgsProject.instance().addMapLayer(ortho)
    QgsProject.instance().addMapLayer(cad)

    # TODO: 여기에 실제 플러그인의 탐지/분류/갱신 로직을 붙여 넣으세요.
    # 예) result = MyPlugin(iface=None).run_update(orthophoto_path, cadastral_path)

    # 완료 로그
    print("✅ headless QGIS logic executed successfully")

    # 결과 반환
    return {
        "status": "success",
        "message": "지도 갱신 완료"
        # 필요시 반환 필드 추가 (new_buildings 경로 등)
    }
