# B6 — Feature table + exploratory classifier

Exploratory only. One known-hoax control and tiny N — accuracies are anecdotal, not an authenticity test.

- Rows: `outputs/feature_table.csv` (12 formations)
- Known-hoax control: Chualar 2013 NVIDIA

## Classifier snapshot

```json
{
  "n_rows": 12,
  "n_hoax": 1,
  "n_candidate": 11,
  "features": [
    "edge_ratio",
    "entropy",
    "fractal_dim",
    "blob_circles_adaptive",
    "circle_line_ratio",
    "stubble_fraction",
    "rot_best",
    "mirror"
  ],
  "train_acc_logistic": 1.0,
  "train_acc_rf": 1.0,
  "logistic_coef": {
    "edge_ratio": 0.074,
    "entropy": 1.1477,
    "fractal_dim": -0.0439,
    "blob_circles_adaptive": -0.1858,
    "circle_line_ratio": -0.7798,
    "stubble_fraction": -0.6948,
    "rot_best": -0.124,
    "mirror": 0.418
  },
  "rf_feature_importance": {
    "edge_ratio": 0.0792,
    "entropy": 0.1984,
    "fractal_dim": 0.1153,
    "blob_circles_adaptive": 0.0658,
    "circle_line_ratio": 0.2089,
    "stubble_fraction": 0.1593,
    "rot_best": 0.1022,
    "mirror": 0.0709
  },
  "in_sample_hoax_proba": {
    "chualar-2013-nvidia": 1.0,
    "stonehenge-julia-1996": 0.13,
    "edmonton-1999": 0.22,
    "eltopia-1998": 0.03,
    "allington-cube-1999": 0.05,
    "milk-hill-2001": 0.05,
    "chilbolton-message-2001": 0.18,
    "crabwood-2002": 0.2,
    "crabwood-disc-crop": 0.07,
    "dna-1996": 0.17,
    "barbury-pi-2008": 0.11,
    "diessenhofen-2008": 0.11
  },
  "loo_acc_logistic": 0.75,
  "loo_note": "LOO folds that drop the sole hoax class are unscored (copied label); treat as anecdotal."
}
```

## Table preview

| id                      | file                                                                   | label      |   width |   height |   edge_ratio |   entropy |   fractal_dim |   hough_circles |   blob_circles_otsu |   blob_circles_adaptive |   blob_circularity_mean |   lines |   circle_line_ratio |   stubble_fraction |   rot_best |   mirror |   mean_intensity |
|:------------------------|:-----------------------------------------------------------------------|:-----------|--------:|---------:|-------------:|----------:|--------------:|----------------:|--------------------:|------------------------:|------------------------:|--------:|--------------------:|-------------------:|-----------:|---------:|-----------------:|
| chualar-2013-nvidia     | chualar_2013_nvidia_hoax.png                                           | known_hoax |    1024 |      683 |      0.31147 |    7.5466 |        1.9424 |             116 |                  26 |                     162 |                  0.4956 |    5062 |              0.032  |             0.243  |     0.9753 |   0.9768 |           146.21 |
| stonehenge-julia-1996   | julia_set_1996_tt_oh.jpg                                               | candidate  |     800 |      533 |      0.32261 |    7.2763 |        1.9566 |              12 |                  82 |                     152 |                  0.5324 |    3722 |              0.0408 |             0.3586 |     0.9772 |   0.9747 |           113.25 |
| edmonton-1999           | edmonton_1999.png                                                      | candidate  |     600 |      324 |      0.323   |    7.4716 |        1.9311 |               0 |                  11 |                      87 |                  0.4885 |    1277 |              0.0681 |             0.498  |     0.9733 |   0.9613 |           149.13 |
| eltopia-1998            | eltopia_1998_iccra.png                                                 | candidate  |     300 |      227 |      0.33323 |    7.1095 |        1.9757 |               0 |                  15 |                      71 |                  0.5059 |     357 |              0.1989 |             0.2996 |     0.971  |   0.9692 |           135.24 |
| allington-cube-1999     | allington_cube_1999_tt.jpg                                             | candidate  |     600 |      425 |      0.12837 |    6.7738 |        1.78   |               0 |                   2 |                      25 |                  0.5279 |     523 |              0.0478 |             0.7148 |     0.9523 |   0.9611 |           102.91 |
| milk-hill-2001          | milk_hill_galaxy_2001_tt_oh.jpg                                        | candidate  |     800 |      542 |      0.10986 |    6.5216 |        1.7414 |              15 |                 101 |                      56 |                  0.4961 |     932 |              0.0601 |             0.9236 |     0.9704 |   0.9682 |           126.44 |
| chilbolton-message-2001 | chilbolton_message_2001_tt.jpg                                         | candidate  |     295 |      600 |      0.35801 |    7.6484 |        1.966  |               1 |                   6 |                      97 |                  0.5208 |    1086 |              0.0893 |             0.4802 |     0.9629 |   0.9644 |           149.31 |
| crabwood-2002           | crabwood_2002_tt_oh2.jpg                                               | candidate  |     800 |      519 |      0.22313 |    6.9108 |        1.8879 |              11 |                  21 |                     185 |                  0.5319 |    2036 |              0.0909 |             0.1053 |     0.9805 |   0.9808 |           119.59 |
| crabwood-disc-crop      | crabwood_2002_disc_crop.png                                            | candidate  |     246 |      246 |      0.23331 |    6.634  |        1.8865 |               0 |                   0 |                      45 |                  0.5552 |     164 |              0.2744 |             0.7567 |     0.9846 |   0.9799 |           124.12 |
| dna-1996                | dna_alton_barnes_1996_tt.jpg                                           | candidate  |     800 |      527 |      0.26202 |    6.8259 |        1.9309 |               1 |                  35 |                     261 |                  0.4852 |    3000 |              0.087  |             0.2401 |     0.9902 |   0.9902 |           100.09 |
| barbury-pi-2008         | barbury_pi_2008.jpg                                                    | candidate  |     800 |      512 |      0.29181 |    6.9624 |        1.9501 |              29 |                  54 |                     235 |                  0.4898 |    3426 |              0.0686 |             0.32   |     0.9807 |   0.9794 |           153.55 |
| diessenhofen-2008       | aerial_view_of_the_crop_circle_in_diessenhofen_15.07.2008_16-44-41.jpg | candidate  |    1236 |      954 |      0.31596 |    7.0862 |        1.9852 |             156 |                 124 |                     432 |                  0.4977 |    8961 |              0.0482 |             0.3425 |     0.9913 |   0.9864 |           148.37 |
