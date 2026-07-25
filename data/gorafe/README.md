# Gorafe megalith landscape — dataset

**Source:** Cabrero González, C., Cámara Serrano, J. A., Esquivel Sánchez, F. J., Spanedda, L., & Garrido Almonacid, A. (2023). A geographical dataset of the Gor River megalithic landscape [Data set]. Zenodo. https://doi.org/10.5281/zenodo.10049759

**License:** CC BY 4.0

**Contents:**
- `Dataset/Gor_data.csv` — 151 preserved dolmens, ~70 variables (coordinates, typology, orientation, terrain, visibility, etc.)
- `Dataset/Gor_LiDAR_data.csv` — 230 LiDAR-identified candidate points (possible destroyed/buried mounds)
- `Dataset/` field explanations and metadata

**Key columns (Gor_data.csv):**
- `Coor_X`, `Coor_Y` — UTM coordinates (ETRS89 UTM 30N, EPSG:25830)
- `Ori_Corr` — corridor orientation (1=N, 2=NE, 3=E, 4=SE, 5=S)
- `Ori_Corr2` — corridor orientation in degrees
- `Ori_Terr`, `Ori_Terr2` — terrain aspect (categorical + degrees)
- `Necrop` — necropolis group
- `Corridor` — presence of corridor
- `Height` — elevation
- `Viewshed_M`, `Viewshed_Km` — viewshed area

**Citation:**
> Cabrero C, Cámara JA, Esquivel FJ, Spanedda L, Almonacid AG (2023). A Geographical Dataset Describing the Complexity of the Gor River Megalithic Landscape. *Journal of Open Archaeology Data*, 11: 14, pp. 1–9. DOI: https://doi.org/10.5334/joad.117
