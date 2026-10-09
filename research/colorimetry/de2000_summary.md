# Delta-E2000 colorimetric stats for the CSS filter covering dataset

Snapshot 2026.10.07, artifact sha256 `bb2d6b5e1696adfa5f6d689fc41d5696868ed4bc37078e35227132f94dd5717a`, generated 2026-10-08T15:58:45Z by `research/colorimetry/de2000_stats.py`. Every number below is recomputable from the dataset artifact alone:

```sh
python3 research/colorimetry/de2000_stats.py scan --jobs 0
```

## The quotable statement

> **integer CSS filters cover sRGB within Delta-E-2000 of 1.096 (measured maximum 1.095415 over all 16777216 rendered colors; mean 0.0281)**

(Strictly: 5 witnesses use a documented fractional parameter; the sentence holds for integer-only chains on the remaining 16,777,211 colors. The fractional exceptions are listed in docs/dataset.md and included in every number here.)

The rendered RGB comes from the independent verifier's model (`research/verifier/verify_covering.py`, the same trust path as the <1% covering claim), converted to CIELAB (D65) and scored with CIEDE2000 against the target. The headline uses the browser-quantized rendering (8-bit codes, what a user sees); the float-model variant is reported alongside. `selftest` reproduces all 34 published test pairs of Sharma/Wu/Dalley 2005 (Table I) and the published sRGB-primary CIELAB anchors within 4-decimal rounding.

## Headline numbers

| quantity | value |
| -------- | ----- |
| colors scored | 16,777,216 |
| max Delta-E2000 (quantized rendering) | 1.095415 at `#231a0b` |
| max Delta-E2000 (float rendering) | 0.653659 at `#051d33` |
| mean Delta-E2000 (quantized) | 0.028139 |
| mean Delta-E2000 (float) | 0.094048 |
| median / p90 / p99 / p99.9 | in buckets [0.0000, 0.0010) / [0.1200, 0.1300) / [0.4100, 0.4200) / [0.6000, 0.6500) |
| per-channel max error, quantized (8-bit code values) | R 1, G 1, B 1 |
| per-channel max error, float (0-255) | R 0.9349, G 0.9358, B 0.9374 |
| rows with nonzero quantized channel error | R 655,989, G 598,511, B 704,357 |

## Distribution of Delta-E2000

| Delta-E2000 below | interpretation (Sharma 2005 / Mahy et al. 1994 published bands) | colors | share |
| ----------------- | --------------------------------------------------------------- | ------ | ----- |
| 0.01 | distinguishable only by instruments | 14,820,753 | 88.3386% |
| 0.10 | imperceptible even to a trained observer | 15,027,894 | 89.5732% |
| 0.25 | small; perceptible to a trained observer | 15,996,200 | 95.3448% |
| 1.00 | perceptible only through very close observation | 16,777,168 | 99.9997% |
| 2.00 | perceptible through close observation (below a JND by most scales) | 16,777,216 | 100.0000% |
| 10.00 | large difference, perceptible at a glance | 16,777,216 | 100.0000% |

Full histogram: 131 buckets over the 130 edges (0.001 to 100; the first bucket is [0, 0.001) and the last is [100, inf)) in `de2000_stats.json`.

## Worst-scoring colors

| rank | color | Delta-E2000 | float | recomputed loss | stored loss | target rgb | rendered int | witness |
| ---- | ----- | ----------- | ----- | --------------- | ----------- | ---------- | ------------ | ------- |
| 1 | `#231a0b` | 1.0954 | 0.5995 | 0.99543 | 0.995434 | 35,26,11 | 35,25,11 | `invert(47%) sepia(4%) saturate(1988%) hue-rotate(357deg) brightness(44%) contrast(136%)` |
| 2 | `#221a08` | 1.0775 | 0.5479 | 0.86103 | 0.861031 | 34,26,8 | 34,25,8 | `invert(68%) sepia(19%) saturate(1931%) hue-rotate(0deg) brightness(11%) contrast(94%)` |
| 3 | `#211501` | 1.0770 | 0.5937 | 0.96854 | 0.968539 | 33,21,1 | 33,22,1 | `invert(8%) sepia(59%) saturate(171%) hue-rotate(0deg) brightness(250%) contrast(150%)` |
| 4 | `#001b23` | 1.0734 | 0.4494 | 0.97336 | 0.973364 | 0,27,35 | 0,26,35 | `invert(89%) sepia(21%) saturate(27078%) hue-rotate(170deg) brightness(19%) contrast(102%)` |
| 5 | `#211702` | 1.0679 | 0.4968 | 0.98396 | 0.983960 | 33,23,2 | 33,24,2 | `invert(89%) sepia(12%) saturate(11727%) hue-rotate(349deg) brightness(13%) contrast(100%)` |
| 6 | `#271c0f` | 1.0674 | 0.5554 | 0.98498 | 0.984977 | 39,28,15 | 39,29,15 | `invert(8%) sepia(1%) saturate(21711%) hue-rotate(354deg) brightness(131%) contrast(97%)` |
| 7 | `#051826` | 1.0541 | 0.5584 | 0.97694 | 0.976938 | 5,24,38 | 5,25,38 | `invert(85%) sepia(16%) saturate(7100%) hue-rotate(175deg) brightness(20%) contrast(117%)` |
| 8 | `#031a28` | 1.0537 | 0.4942 | 0.83204 | 0.832042 | 3,26,40 | 3,25,40 | `invert(83%) sepia(38%) saturate(10349%) hue-rotate(177deg) brightness(16%) contrast(101%)` |
| 9 | `#001a23` | 1.0485 | 0.4534 | 0.87990 | 0.879896 | 0,26,35 | 0,25,35 | `invert(18%) sepia(76%) saturate(11987%) hue-rotate(182deg) brightness(59%) contrast(160%)` |
| 10 | `#041826` | 1.0463 | 0.5479 | 0.98692 | 0.986918 | 4,24,38 | 4,25,38 | `invert(10%) sepia(85%) saturate(970%) hue-rotate(174deg) brightness(59%) contrast(98%)` |
| 11 | `#292114` | 1.0446 | 0.5205 | 0.98331 | 0.983312 | 41,33,20 | 41,34,20 | `invert(67%) sepia(4%) saturate(7853%) hue-rotate(0deg) brightness(11%) contrast(86%)` |
| 12 | `#071720` | 1.0446 | 0.5442 | 0.97032 | 0.970318 | 7,23,32 | 7,24,32 | `invert(60%) sepia(26%) saturate(6018%) hue-rotate(170deg) brightness(11%) contrast(96%)` |
| 13 | `#001a26` | 1.0436 | 0.6152 | 0.85177 | 0.851774 | 0,26,38 | 0,25,38 | `invert(92%) sepia(8%) saturate(23519%) hue-rotate(156deg) brightness(23%) contrast(130%)` |
| 14 | `#182431` | 1.0366 | 0.5244 | 0.94574 | 0.945736 | 24,36,49 | 24,35,49 | `invert(90%) sepia(34%) saturate(21017%) hue-rotate(191deg) brightness(15%) contrast(88%)` |
| 15 | `#061724` | 1.0353 | 0.4567 | 0.95609 | 0.956091 | 6,23,36 | 6,24,36 | `invert(49%) sepia(15%) saturate(3326%) hue-rotate(168deg) brightness(14%) contrast(98%)` |
| 16 | `#081a27` | 1.0345 | 0.5670 | 0.87769 | 0.877686 | 8,26,39 | 8,27,39 | `invert(11%) sepia(84%) saturate(74%) hue-rotate(161deg) brightness(217%) contrast(187%)` |
| 17 | `#0c1c2b` | 1.0343 | 0.5291 | 0.99109 | 0.991087 | 12,28,43 | 12,29,43 | `invert(85%) sepia(24%) saturate(20249%) hue-rotate(189deg) brightness(14%) contrast(92%)` |
| 18 | `#231800` | 1.0295 | 0.5231 | 0.97270 | 0.972700 | 35,24,0 | 35,25,0 | `invert(34%) sepia(81%) saturate(4675%) hue-rotate(52deg) brightness(73%) contrast(221%)` |
| 19 | `#251600` | 1.0293 | 0.5285 | 0.88661 | 0.886613 | 37,22,0 | 37,23,0 | `invert(15%) sepia(100%) saturate(4714%) hue-rotate(59deg) brightness(51%) contrast(122%)` |
| 20 | `#0e1c2c` | 1.0286 | 0.5142 | 0.98143 | 0.981434 | 14,28,44 | 14,27,44 | `invert(41%) sepia(8%) saturate(8708%) hue-rotate(186deg) brightness(16%) contrast(93%)` |
| 21 | `#0f1b2c` | 1.0285 | 0.6058 | 0.98537 | 0.985373 | 15,27,44 | 15,28,44 | `invert(49%) sepia(19%) saturate(14967%) hue-rotate(201deg) brightness(14%) contrast(91%)` |
| 22 | `#011b28` | 1.0283 | 0.5147 | 0.90870 | 0.908698 | 1,27,40 | 1,26,40 | `invert(63%) sepia(9%) saturate(11816%) hue-rotate(171deg) brightness(17%) contrast(104%)` |
| 23 | `#0d1d28` | 1.0254 | 0.4965 | 0.98292 | 0.982921 | 13,29,40 | 13,30,40 | `invert(38%) sepia(7%) saturate(1134%) hue-rotate(160deg) brightness(57%) contrast(141%)` |
| 24 | `#5a595a` | 1.0236 | 0.5367 | 0.97792 | 0.977921 | 90,89,90 | 90,90,90 | `invert(87%) sepia(42%) saturate(9590%) hue-rotate(259deg) brightness(1%) contrast(30%)` |
| 25 | `#0e1e2a` | 1.0229 | 0.5537 | 0.97484 | 0.974841 | 14,30,42 | 14,31,42 | `invert(11%) sepia(98%) saturate(9131%) hue-rotate(196deg) brightness(19%) contrast(89%)` |
| 26 | `#251900` | 1.0209 | 0.5588 | 0.82968 | 0.829675 | 37,25,0 | 37,24,0 | `invert(4%) sepia(58%) saturate(6468%) hue-rotate(59deg) brightness(209%) contrast(123%)` |
| 27 | `#3f362b` | 1.0204 | 0.5157 | 0.96071 | 0.960708 | 63,54,43 | 63,53,43 | `invert(56%) sepia(5%) saturate(8119%) hue-rotate(353deg) brightness(13%) contrast(67%)` |
| 28 | `#001822` | 1.0201 | 0.5194 | 0.97171 | 0.971708 | 0,24,34 | 0,25,34 | `invert(54%) sepia(73%) saturate(21557%) hue-rotate(183deg) brightness(53%) contrast(145%)` |
| 29 | `#291a0f` | 1.0198 | 0.5166 | 0.85972 | 0.859715 | 41,26,15 | 41,27,15 | `invert(20%) sepia(50%) saturate(969%) hue-rotate(348deg) brightness(31%) contrast(90%)` |
| 30 | `#2b1d0f` | 1.0194 | 0.5318 | 0.93508 | 0.935077 | 43,29,15 | 43,30,15 | `invert(100%) sepia(5%) saturate(8883%) hue-rotate(305deg) brightness(35%) contrast(221%)` |
| 31 | `#001b29` | 1.0188 | 0.5032 | 0.77205 | 0.772054 | 0,27,41 | 0,26,41 | `invert(63%) sepia(86%) saturate(5093%) hue-rotate(159deg) brightness(32%) contrast(138%)` |
| 32 | `#0f1e2e` | 1.0184 | 0.5633 | 0.87816 | 0.878160 | 15,30,46 | 15,29,46 | `invert(69%) sepia(64%) saturate(6253%) hue-rotate(193deg) brightness(16%) contrast(94%)` |
| 33 | `#1e1700` | 1.0166 | 0.5464 | 0.84294 | 0.842937 | 30,23,0 | 30,24,0 | `invert(15%) sepia(13%) saturate(16985%) hue-rotate(57deg) brightness(150%) contrast(300%)` |
| 34 | `#1d1805` | 1.0123 | 0.4897 | 0.94695 | 0.946946 | 29,24,5 | 29,25,5 | `invert(95%) sepia(17%) saturate(3252%) hue-rotate(334deg) brightness(11%) contrast(99%)` |
| 35 | `#0b1b2d` | 1.0075 | 0.5776 | 0.91300 | 0.913000 | 11,27,45 | 11,28,45 | `invert(4%) sepia(66%) saturate(938%) hue-rotate(178deg) brightness(174%) contrast(96%)` |
| 36 | `#021d23` | 1.0074 | 0.5079 | 0.94209 | 0.942089 | 2,29,35 | 2,28,35 | `invert(83%) sepia(65%) saturate(175%) hue-rotate(159deg) brightness(31%) contrast(191%)` |
| 37 | `#261603` | 1.0068 | 0.6307 | 0.96617 | 0.966166 | 38,22,3 | 38,21,3 | `invert(37%) sepia(3%) saturate(1833%) hue-rotate(351deg) brightness(79%) contrast(198%)` |
| 38 | `#101f30` | 1.0067 | 0.5995 | 0.96086 | 0.960864 | 16,31,48 | 16,32,48 | `invert(8%) sepia(7%) saturate(4924%) hue-rotate(170deg) brightness(112%) contrast(94%)` |
| 39 | `#3b2f25` | 1.0057 | 0.4922 | 0.94299 | 0.942989 | 59,47,37 | 59,46,37 | `invert(12%) sepia(96%) saturate(1322%) hue-rotate(10deg) brightness(38%) contrast(71%)` |
| 40 | `#281c05` | 1.0035 | 0.5184 | 0.90083 | 0.900835 | 40,28,5 | 40,27,5 | `invert(8%) sepia(1%) saturate(25191%) hue-rotate(360deg) brightness(158%) contrast(104%)` |
| 41 | `#091d2b` | 1.0021 | 0.5688 | 0.99177 | 0.991775 | 9,29,43 | 9,30,43 | `invert(73%) sepia(11%) saturate(6229%) hue-rotate(175deg) brightness(19%) contrast(107%)` |
| 42 | `#0f1d2f` | 1.0019 | 0.5455 | 0.87696 | 0.876956 | 15,29,47 | 15,30,47 | `invert(13%) sepia(25%) saturate(3839%) hue-rotate(192deg) brightness(46%) contrast(91%)` |
| 43 | `#383123` | 1.0014 | 0.5069 | 0.96375 | 0.963751 | 56,49,35 | 56,48,35 | `invert(20%) sepia(28%) saturate(140%) hue-rotate(360deg) brightness(150%) contrast(169%)` |
| 44 | `#2a1b0e` | 1.0014 | 0.5064 | 0.98391 | 0.983906 | 42,27,14 | 42,26,14 | `invert(1%) sepia(37%) saturate(16167%) hue-rotate(52deg) brightness(258%) contrast(89%)` |
| 45 | `#0f2030` | 1.0011 | 0.5657 | 0.92928 | 0.929278 | 15,32,48 | 15,33,48 | `invert(3%) sepia(15%) saturate(3488%) hue-rotate(173deg) brightness(264%) contrast(92%)` |
| 46 | `#0b1d2e` | 1.0007 | 0.5803 | 0.99591 | 0.995906 | 11,29,46 | 11,28,46 | `invert(21%) sepia(29%) saturate(4287%) hue-rotate(194deg) brightness(26%) contrast(92%)` |
| 47 | `#1e1500` | 1.0002 | 0.5992 | 0.95143 | 0.951431 | 30,21,0 | 30,20,0 | `invert(88%) sepia(13%) saturate(16923%) hue-rotate(15deg) brightness(30%) contrast(149%)` |
| 48 | `#3a2e21` | 1.0002 | 0.5044 | 0.98642 | 0.986423 | 58,46,33 | 58,45,33 | `invert(5%) sepia(2%) saturate(17432%) hue-rotate(349deg) brightness(171%) contrast(76%)` |
| 49 | `#2c1f0d` | 0.9986 | 0.4868 | 0.88879 | 0.888791 | 44,31,13 | 44,30,13 | `invert(78%) sepia(92%) saturate(15069%) hue-rotate(353deg) brightness(14%) contrast(91%)` |
| 50 | `#322517` | 0.9977 | 0.5038 | 0.98922 | 0.989223 | 50,37,23 | 50,36,23 | `invert(14%) sepia(24%) saturate(1520%) hue-rotate(349deg) brightness(57%) contrast(84%)` |
| 51 | `#29343d` | 0.9971 | 0.5048 | 0.99699 | 0.996989 | 41,52,61 | 41,51,61 | `invert(17%) sepia(8%) saturate(228%) hue-rotate(167deg) brightness(222%) contrast(262%)` |
| 52 | `#08151e` | 0.9970 | 0.4939 | 0.94377 | 0.943767 | 8,21,30 | 8,22,30 | `invert(10%) sepia(2%) saturate(27547%) hue-rotate(168deg) brightness(51%) contrast(95%)` |
| 53 | `#18272e` | 0.9965 | 0.4706 | 0.96557 | 0.965572 | 24,39,46 | 24,38,46 | `invert(74%) sepia(16%) saturate(18279%) hue-rotate(170deg) brightness(11%) contrast(82%)` |
| 54 | `#071a2c` | 0.9951 | 0.5018 | 0.98531 | 0.985308 | 7,26,44 | 7,25,44 | `invert(51%) sepia(4%) saturate(6262%) hue-rotate(169deg) brightness(24%) contrast(109%)` |
| 55 | `#2b1f0c` | 0.9933 | 0.4973 | 0.81616 | 0.816157 | 43,31,12 | 43,32,12 | `invert(13%) sepia(1%) saturate(22921%) hue-rotate(359deg) brightness(98%) contrast(100%)` |
| 56 | `#031b2b` | 0.9933 | 0.5096 | 0.93246 | 0.932457 | 3,27,43 | 3,26,43 | `invert(68%) sepia(15%) saturate(9888%) hue-rotate(178deg) brightness(19%) contrast(107%)` |
| 57 | `#041b28` | 0.9913 | 0.5279 | 0.98941 | 0.989407 | 4,27,40 | 4,28,40 | `invert(45%) sepia(84%) saturate(984%) hue-rotate(171deg) brightness(15%) contrast(98%)` |
| 58 | `#3d3528` | 0.9901 | 0.4929 | 0.98499 | 0.984988 | 61,53,40 | 61,54,40 | `invert(4%) sepia(4%) saturate(8748%) hue-rotate(0deg) brightness(206%) contrast(69%)` |
| 59 | `#44382d` | 0.9898 | 0.5242 | 0.95694 | 0.956941 | 68,56,45 | 68,55,45 | `invert(93%) sepia(98%) saturate(504%) hue-rotate(302deg) brightness(28%) contrast(106%)` |
| 60 | `#1a2831` | 0.9894 | 0.5453 | 0.99427 | 0.994271 | 26,40,49 | 26,41,49 | `invert(67%) sepia(13%) saturate(18369%) hue-rotate(174deg) brightness(12%) contrast(81%)` |
| 61 | `#071a2d` | 0.9889 | 0.5375 | 0.99276 | 0.992756 | 7,26,45 | 7,27,45 | `invert(51%) sepia(44%) saturate(5392%) hue-rotate(190deg) brightness(17%) contrast(98%)` |
| 62 | `#001c29` | 0.9858 | 0.6396 | 0.95686 | 0.956862 | 0,28,41 | 0,27,41 | `invert(73%) sepia(71%) saturate(20615%) hue-rotate(188deg) brightness(37%) contrast(112%)` |
| 63 | `#011827` | 0.9855 | 0.5195 | 0.97778 | 0.977782 | 1,24,39 | 1,23,39 | `invert(15%) sepia(2%) saturate(20633%) hue-rotate(164deg) brightness(59%) contrast(103%)` |
| 64 | `#2f2312` | 0.9849 | 0.4633 | 0.93923 | 0.939227 | 47,35,18 | 47,36,18 | `invert(32%) sepia(52%) saturate(253%) hue-rotate(357deg) brightness(55%) contrast(117%)` |
| 65 | `#0e2026` | 0.9848 | 0.5024 | 0.99356 | 0.993560 | 14,32,38 | 14,33,38 | `invert(80%) sepia(82%) saturate(29273%) hue-rotate(161deg) brightness(12%) contrast(89%)` |
| 66 | `#282110` | 0.9845 | 0.5078 | 0.98429 | 0.984291 | 40,33,16 | 40,34,16 | `invert(85%) sepia(19%) saturate(6055%) hue-rotate(354deg) brightness(11%) contrast(88%)` |
| 67 | `#071726` | 0.9837 | 0.5649 | 0.91742 | 0.917422 | 7,23,38 | 7,22,38 | `invert(7%) sepia(11%) saturate(9049%) hue-rotate(190deg) brightness(77%) contrast(96%)` |
| 68 | `#2a1e07` | 0.9833 | 0.5047 | 0.84210 | 0.842099 | 42,30,7 | 42,29,7 | `invert(4%) sepia(2%) saturate(17572%) hue-rotate(360deg) brightness(248%) contrast(95%)` |
| 69 | `#162536` | 0.9822 | 0.5592 | 0.88934 | 0.889340 | 22,37,54 | 22,38,54 | `invert(75%) sepia(14%) saturate(17103%) hue-rotate(187deg) brightness(19%) contrast(93%)` |
| 70 | `#585a58` | 0.9817 | 0.5093 | 0.99894 | 0.998940 | 88,90,88 | 88,89,88 | `invert(75%) sepia(37%) saturate(30000%) hue-rotate(139deg) brightness(4%) contrast(31%)` |
| 71 | `#554b41` | 0.9815 | 0.4885 | 0.98015 | 0.980148 | 85,75,65 | 85,76,65 | `invert(70%) sepia(59%) saturate(8717%) hue-rotate(21deg) brightness(20%) contrast(49%)` |
| 72 | `#23303e` | 0.9811 | 0.4908 | 0.96917 | 0.969166 | 35,48,62 | 35,47,62 | `invert(12%) sepia(18%) saturate(7926%) hue-rotate(200deg) brightness(41%) contrast(73%)` |
| 73 | `#322415` | 0.9794 | 0.5426 | 0.95367 | 0.953667 | 50,36,21 | 50,35,21 | `invert(15%) sepia(4%) saturate(13770%) hue-rotate(357deg) brightness(51%) contrast(84%)` |
| 74 | `#061c2e` | 0.9788 | 0.4698 | 0.92341 | 0.923414 | 6,28,46 | 6,27,46 | `invert(62%) sepia(55%) saturate(5725%) hue-rotate(186deg) brightness(18%) contrast(100%)` |
| 75 | `#1e2d37` | 0.9779 | 0.5318 | 0.97335 | 0.973353 | 30,45,55 | 30,44,55 | `invert(52%) sepia(4%) saturate(19532%) hue-rotate(181deg) brightness(14%) contrast(79%)` |
| 76 | `#081c2f` | 0.9775 | 0.5181 | 0.82888 | 0.828882 | 8,28,47 | 8,29,47 | `invert(23%) sepia(2%) saturate(21386%) hue-rotate(170deg) brightness(41%) contrast(99%)` |
| 77 | `#00192b` | 0.9773 | 0.5061 | 0.86250 | 0.862496 | 0,25,43 | 0,24,43 | `invert(6%) sepia(74%) saturate(4103%) hue-rotate(175deg) brightness(172%) contrast(179%)` |
| 78 | `#11242d` | 0.9763 | 0.5257 | 0.99397 | 0.993975 | 17,36,45 | 17,35,45 | `invert(49%) sepia(1%) saturate(4696%) hue-rotate(156deg) brightness(60%) contrast(182%)` |
| 79 | `#1a2436` | 0.9757 | 0.4368 | 0.99497 | 0.994975 | 26,36,54 | 26,37,54 | `invert(2%) sepia(34%) saturate(6424%) hue-rotate(214deg) brightness(172%) contrast(80%)` |
| 80 | `#2a1a03` | 0.9733 | 0.4795 | 0.88561 | 0.885613 | 42,26,3 | 42,27,3 | `invert(64%) sepia(49%) saturate(410%) hue-rotate(357deg) brightness(24%) contrast(118%)` |
| 81 | `#211401` | 0.9720 | 0.4447 | 0.94216 | 0.942160 | 33,20,1 | 33,19,1 | `invert(73%) sepia(75%) saturate(729%) hue-rotate(330deg) brightness(15%) contrast(106%)` |
| 82 | `#05192d` | 0.9720 | 0.4680 | 0.93980 | 0.939799 | 5,25,45 | 5,26,45 | `invert(80%) sepia(1%) saturate(7346%) hue-rotate(168deg) brightness(34%) contrast(181%)` |
| 83 | `#0b212b` | 0.9706 | 0.5272 | 0.95877 | 0.958769 | 11,33,43 | 11,32,43 | `invert(3%) sepia(9%) saturate(6713%) hue-rotate(165deg) brightness(246%) contrast(92%)` |
| 84 | `#271501` | 0.9676 | 0.5117 | 0.82107 | 0.821071 | 39,21,1 | 39,20,1 | `invert(10%) sepia(3%) saturate(10026%) hue-rotate(350deg) brightness(109%) contrast(105%)` |
| 85 | `#2b190b` | 0.9666 | 0.5301 | 0.98116 | 0.981161 | 43,25,11 | 43,26,11 | `invert(78%) sepia(20%) saturate(17348%) hue-rotate(357deg) brightness(14%) contrast(92%)` |
| 86 | `#271b00` | 0.9652 | 0.5326 | 0.80615 | 0.806153 | 39,27,0 | 39,28,0 | `invert(99%) sepia(7%) saturate(24803%) hue-rotate(350deg) brightness(36%) contrast(248%)` |
| 87 | `#261b00` | 0.9652 | 0.4393 | 0.95091 | 0.950905 | 38,27,0 | 38,28,0 | `invert(90%) sepia(4%) saturate(22835%) hue-rotate(0deg) brightness(19%) contrast(113%)` |
| 88 | `#001d28` | 0.9643 | 0.5490 | 0.86302 | 0.863022 | 0,29,40 | 0,28,40 | `invert(27%) sepia(92%) saturate(1153%) hue-rotate(159deg) brightness(40%) contrast(125%)` |
| 89 | `#313d48` | 0.9636 | 0.5048 | 0.95559 | 0.955589 | 49,61,72 | 49,60,72 | `invert(92%) sepia(4%) saturate(21548%) hue-rotate(178deg) brightness(25%) contrast(87%)` |
| 90 | `#281c02` | 0.9636 | 0.4811 | 0.91807 | 0.918069 | 40,28,2 | 40,29,2 | `invert(86%) sepia(1%) saturate(15563%) hue-rotate(360deg) brightness(23%) contrast(127%)` |
| 91 | `#281600` | 0.9626 | 0.4684 | 0.98212 | 0.982119 | 40,22,0 | 40,21,0 | `invert(15%) sepia(31%) saturate(18993%) hue-rotate(58deg) brightness(41%) contrast(107%)` |
| 92 | `#2a190d` | 0.9622 | 0.5283 | 0.99549 | 0.995493 | 42,25,13 | 42,24,13 | `invert(7%) sepia(41%) saturate(2327%) hue-rotate(359deg) brightness(76%) contrast(90%)` |
| 93 | `#281c00` | 0.9620 | 0.4019 | 0.93415 | 0.934148 | 40,28,0 | 40,27,0 | `invert(79%) sepia(51%) saturate(9435%) hue-rotate(28deg) brightness(24%) contrast(104%)` |
| 94 | `#1b2b34` | 0.9618 | 0.4975 | 0.91678 | 0.916784 | 27,43,52 | 27,44,52 | `invert(89%) sepia(16%) saturate(23526%) hue-rotate(170deg) brightness(13%) contrast(80%)` |
| 95 | `#3b2d1d` | 0.9617 | 0.5903 | 0.97654 | 0.976538 | 59,45,29 | 59,46,29 | `invert(75%) sepia(60%) saturate(4002%) hue-rotate(350deg) brightness(16%) contrast(79%)` |
| 96 | `#2a1802` | 0.9613 | 0.4469 | 0.95540 | 0.955396 | 42,24,2 | 42,25,2 | `invert(74%) sepia(70%) saturate(787%) hue-rotate(328deg) brightness(19%) contrast(108%)` |
| 97 | `#2e220e` | 0.9599 | 0.4279 | 0.94976 | 0.949757 | 46,34,14 | 46,35,14 | `invert(20%) sepia(19%) saturate(5631%) hue-rotate(27deg) brightness(39%) contrast(89%)` |
| 98 | `#041e20` | 0.9587 | 0.5034 | 0.87865 | 0.878655 | 4,30,32 | 4,29,32 | `invert(5%) sepia(24%) saturate(1503%) hue-rotate(137deg) brightness(157%) contrast(97%)` |
| 99 | `#2c1d06` | 0.9584 | 0.3961 | 0.96712 | 0.967122 | 44,29,6 | 44,30,6 | `invert(24%) sepia(1%) saturate(18238%) hue-rotate(358deg) brightness(71%) contrast(115%)` |
| 100 | `#2a1d04` | 0.9584 | 0.4557 | 0.88775 | 0.887752 | 42,29,4 | 42,30,4 | `invert(14%) sepia(8%) saturate(2071%) hue-rotate(2deg) brightness(130%) contrast(121%)` |
| 101 | `#0a2024` | 0.9582 | 0.5115 | 0.92122 | 0.921219 | 10,32,36 | 10,31,36 | `invert(10%) sepia(1%) saturate(30000%) hue-rotate(143deg) brightness(86%) contrast(95%)` |
| 102 | `#1a293b` | 0.9575 | 0.4804 | 0.90769 | 0.907695 | 26,41,59 | 26,42,59 | `invert(100%) sepia(21%) saturate(4933%) hue-rotate(175deg) brightness(39%) contrast(244%)` |
| 103 | `#36414e` | 0.9571 | 0.4902 | 0.99148 | 0.991479 | 54,65,78 | 54,64,78 | `invert(59%) sepia(4%) saturate(11748%) hue-rotate(188deg) brightness(21%) contrast(67%)` |
| 104 | `#2f1f0d` | 0.9569 | 0.5783 | 0.93264 | 0.932642 | 47,31,13 | 47,30,13 | `invert(5%) sepia(2%) saturate(28623%) hue-rotate(359deg) brightness(166%) contrast(90%)` |
| 105 | `#2a1c01` | 0.9557 | 0.4961 | 0.85257 | 0.852572 | 42,28,1 | 42,27,1 | `invert(83%) sepia(1%) saturate(15189%) hue-rotate(0deg) brightness(24%) contrast(129%)` |
| 106 | `#37271c` | 0.9550 | 0.5169 | 0.94068 | 0.940679 | 55,39,28 | 55,38,28 | `invert(72%) sepia(19%) saturate(18786%) hue-rotate(355deg) brightness(14%) contrast(79%)` |
| 107 | `#3b3220` | 0.9546 | 0.4932 | 0.94923 | 0.949233 | 59,50,32 | 59,49,32 | `invert(100%) sepia(16%) saturate(2499%) hue-rotate(313deg) brightness(36%) contrast(192%)` |
| 108 | `#757375` | 0.9532 | 0.4642 | 0.94407 | 0.944066 | 117,115,117 | 117,116,117 | `invert(73%) sepia(23%) saturate(14947%) hue-rotate(265deg) brightness(9%) contrast(10%)` |
| 109 | `#26353c` | 0.9531 | 0.4710 | 0.95575 | 0.955745 | 38,53,60 | 38,52,60 | `invert(25%) sepia(1%) saturate(4591%) hue-rotate(156deg) brightness(117%) contrast(147%)` |
| 110 | `#082032` | 0.9529 | 0.5863 | 0.93247 | 0.932475 | 8,32,50 | 8,33,50 | `invert(31%) sepia(2%) saturate(13756%) hue-rotate(162deg) brightness(42%) contrast(105%)` |
| 111 | `#1f1a00` | 0.9526 | 0.5319 | 0.91353 | 0.913529 | 31,26,0 | 31,25,0 | `invert(49%) sepia(19%) saturate(2772%) hue-rotate(21deg) brightness(21%) contrast(104%)` |
| 112 | `#22313b` | 0.9517 | 0.5238 | 0.99863 | 0.998627 | 34,49,59 | 34,50,59 | `invert(18%) sepia(14%) saturate(5012%) hue-rotate(172deg) brightness(37%) contrast(74%)` |
| 113 | `#3a4351` | 0.9514 | 0.4631 | 0.93285 | 0.932853 | 58,67,81 | 58,66,81 | `invert(35%) sepia(70%) saturate(3665%) hue-rotate(209deg) brightness(18%) contrast(57%)` |
| 114 | `#07212e` | 0.9513 | 0.3649 | 0.95221 | 0.952211 | 7,33,46 | 7,32,46 | `invert(6%) sepia(2%) saturate(26966%) hue-rotate(164deg) brightness(150%) contrast(96%)` |
| 115 | `#152839` | 0.9505 | 0.4349 | 0.94121 | 0.941208 | 21,40,57 | 21,39,57 | `invert(4%) sepia(88%) saturate(1538%) hue-rotate(192deg) brightness(139%) contrast(84%)` |
| 116 | `#192c38` | 0.9479 | 0.5019 | 0.96551 | 0.965513 | 25,44,56 | 25,43,56 | `invert(79%) sepia(50%) saturate(7107%) hue-rotate(178deg) brightness(17%) contrast(85%)` |
| 117 | `#082230` | 0.9479 | 0.4084 | 0.86328 | 0.863279 | 8,34,48 | 8,33,48 | `invert(93%) sepia(3%) saturate(3605%) hue-rotate(172deg) brightness(36%) contrast(223%)` |
| 118 | `#302510` | 0.9468 | 0.4237 | 0.92595 | 0.925946 | 48,37,16 | 48,36,16 | `invert(76%) sepia(72%) saturate(115%) hue-rotate(360deg) brightness(31%) contrast(155%)` |
| 119 | `#011c2f` | 0.9457 | 0.4276 | 0.92743 | 0.927434 | 1,28,47 | 1,27,47 | `invert(84%) sepia(15%) saturate(27505%) hue-rotate(182deg) brightness(19%) contrast(102%)` |
| 120 | `#253143` | 0.9450 | 0.5098 | 0.89396 | 0.893957 | 37,49,67 | 37,50,67 | `invert(10%) sepia(58%) saturate(3951%) hue-rotate(209deg) brightness(40%) contrast(71%)` |
| 121 | `#2e210b` | 0.9447 | 0.4651 | 0.78343 | 0.783427 | 46,33,11 | 46,34,11 | `invert(9%) sepia(53%) saturate(631%) hue-rotate(360deg) brightness(116%) contrast(95%)` |
| 122 | `#021e28` | 0.9440 | 0.5510 | 0.91784 | 0.917837 | 2,30,40 | 2,29,40 | `invert(20%) sepia(3%) saturate(8249%) hue-rotate(151deg) brightness(64%) contrast(109%)` |
| 123 | `#2c1a06` | 0.9439 | 0.4880 | 0.97857 | 0.978565 | 44,26,6 | 44,25,6 | `invert(19%) sepia(5%) saturate(4489%) hue-rotate(350deg) brightness(74%) contrast(109%)` |
| 124 | `#261e03` | 0.9436 | 0.4903 | 0.99151 | 0.991515 | 38,30,3 | 38,29,3 | `invert(92%) sepia(26%) saturate(146%) hue-rotate(1deg) brightness(38%) contrast(291%)` |
| 125 | `#001d2f` | 0.9429 | 0.4361 | 0.96404 | 0.964035 | 0,29,47 | 0,28,47 | `invert(85%) sepia(68%) saturate(21362%) hue-rotate(169deg) brightness(36%) contrast(226%)` |
| 126 | `#483830` | 0.9428 | 0.5318 | 0.98815 | 0.988155 | 72,56,48 | 72,57,48 | `invert(60%) sepia(84%) saturate(4313%) hue-rotate(351deg) brightness(16%) contrast(64%)` |
| 127 | `#6f665b` | 0.9426 | 0.4936 | 0.98885 | 0.988850 | 111,102,91 | 111,103,91 | `invert(24%) sepia(16%) saturate(2139%) hue-rotate(355deg) brightness(75%) contrast(30%)` |
| 128 | `#141f32` | 0.9423 | 0.4948 | 0.83749 | 0.837490 | 20,31,50 | 20,30,50 | `invert(12%) sepia(15%) saturate(5238%) hue-rotate(196deg) brightness(55%) contrast(90%)` |
| 129 | `#4e4536` | 0.9412 | 0.4082 | 0.99099 | 0.990988 | 78,69,54 | 78,70,54 | `invert(14%) sepia(3%) saturate(11687%) hue-rotate(0deg) brightness(80%) contrast(58%)` |
| 130 | `#2b2008` | 0.9405 | 0.4390 | 0.94074 | 0.940742 | 43,32,8 | 43,33,8 | `invert(17%) sepia(6%) saturate(1581%) hue-rotate(4deg) brightness(144%) contrast(147%)` |
| 131 | `#151f33` | 0.9404 | 0.4876 | 0.84390 | 0.843902 | 21,31,51 | 21,32,51 | `invert(84%) sepia(11%) saturate(24858%) hue-rotate(194deg) brightness(20%) contrast(100%)` |
| 132 | `#001727` | 0.9403 | 0.3481 | 0.97320 | 0.973198 | 0,23,39 | 0,22,39 | `invert(18%) sepia(29%) saturate(2328%) hue-rotate(146deg) brightness(132%) contrast(275%)` |
| 133 | `#0f2236` | 0.9400 | 0.4738 | 0.81708 | 0.817080 | 15,34,54 | 15,35,54 | `invert(35%) sepia(8%) saturate(2996%) hue-rotate(169deg) brightness(40%) contrast(105%)` |
| 134 | `#001e2c` | 0.9387 | 0.4260 | 0.93857 | 0.938575 | 0,30,44 | 0,29,44 | `invert(94%) sepia(77%) saturate(30000%) hue-rotate(169deg) brightness(33%) contrast(193%)` |
| 135 | `#2c3a48` | 0.9385 | 0.5343 | 0.98089 | 0.980887 | 44,58,72 | 44,59,72 | `invert(75%) sepia(87%) saturate(6800%) hue-rotate(192deg) brightness(17%) contrast(66%)` |
| 136 | `#493a2a` | 0.9380 | 0.4172 | 0.97956 | 0.979564 | 73,58,42 | 73,59,42 | `invert(9%) sepia(6%) saturate(30000%) hue-rotate(35deg) brightness(87%) contrast(67%)` |
| 137 | `#0c1d32` | 0.9379 | 0.4461 | 0.96504 | 0.965036 | 12,29,50 | 12,30,50 | `invert(2%) sepia(20%) saturate(7424%) hue-rotate(201deg) brightness(269%) contrast(91%)` |
| 138 | `#5d5648` | 0.9366 | 0.4717 | 0.98246 | 0.982459 | 93,86,72 | 93,85,72 | `invert(10%) sepia(1%) saturate(18541%) hue-rotate(360deg) brightness(199%) contrast(54%)` |
| 139 | `#384550` | 0.9361 | 0.4770 | 0.87131 | 0.871308 | 56,69,80 | 56,68,80 | `invert(34%) sepia(64%) saturate(903%) hue-rotate(174deg) brightness(24%) contrast(59%)` |
| 140 | `#151e32` | 0.9356 | 0.5349 | 0.99864 | 0.998643 | 21,30,50 | 21,31,50 | `invert(6%) sepia(20%) saturate(1488%) hue-rotate(182deg) brightness(162%) contrast(96%)` |
| 141 | `#001e28` | 0.9352 | 0.4726 | 0.72491 | 0.724912 | 0,30,40 | 0,29,40 | `invert(58%) sepia(100%) saturate(4261%) hue-rotate(160deg) brightness(26%) contrast(117%)` |
| 142 | `#25353c` | 0.9349 | 0.4841 | 0.94352 | 0.943518 | 37,53,60 | 37,54,60 | `invert(1%) sepia(58%) saturate(7546%) hue-rotate(186deg) brightness(291%) contrast(71%)` |
| 143 | `#0e1b30` | 0.9348 | 0.4938 | 0.94292 | 0.942923 | 14,27,48 | 14,28,48 | `invert(13%) sepia(41%) saturate(5834%) hue-rotate(212deg) brightness(27%) contrast(89%)` |
| 144 | `#182336` | 0.9347 | 0.4627 | 0.93641 | 0.936414 | 24,35,54 | 24,34,54 | `invert(18%) sepia(5%) saturate(11756%) hue-rotate(190deg) brightness(43%) contrast(88%)` |
| 145 | `#2a1700` | 0.9346 | 0.4261 | 0.82465 | 0.824652 | 42,23,0 | 42,22,0 | `invert(85%) sepia(59%) saturate(24902%) hue-rotate(4deg) brightness(32%) contrast(170%)` |
| 146 | `#3d2d1c` | 0.9346 | 0.4735 | 0.82300 | 0.823000 | 61,45,28 | 61,46,28 | `invert(65%) sepia(8%) saturate(14732%) hue-rotate(355deg) brightness(17%) contrast(79%)` |
| 147 | `#666466` | 0.9343 | 0.4997 | 0.92026 | 0.920261 | 102,100,102 | 102,99,102 | `invert(93%) sepia(94%) saturate(25394%) hue-rotate(212deg) brightness(13%) contrast(27%)` |
| 148 | `#021d31` | 0.9341 | 0.4984 | 0.99048 | 0.990476 | 2,29,49 | 2,30,49 | `invert(13%) sepia(4%) saturate(1664%) hue-rotate(162deg) brightness(234%) contrast(208%)` |
| 149 | `#362e1c` | 0.9340 | 0.4315 | 0.91565 | 0.915651 | 54,46,28 | 54,47,28 | `invert(80%) sepia(22%) saturate(955%) hue-rotate(360deg) brightness(18%) contrast(90%)` |
| 150 | `#001d30` | 0.9338 | 0.4764 | 0.78021 | 0.780207 | 0,29,48 | 0,30,48 | `invert(9%) sepia(14%) saturate(6975%) hue-rotate(176deg) brightness(99%) contrast(103%)` |
| 151 | `#253643` | 0.9337 | 0.4676 | 0.99617 | 0.996173 | 37,54,67 | 37,53,67 | `invert(71%) sepia(27%) saturate(17951%) hue-rotate(189deg) brightness(17%) contrast(71%)` |
| 152 | `#062133` | 0.9332 | 0.4394 | 0.85000 | 0.849999 | 6,33,51 | 6,34,51 | `invert(9%) sepia(58%) saturate(242%) hue-rotate(160deg) brightness(225%) contrast(142%)` |
| 153 | `#625647` | 0.9326 | 0.4578 | 0.92914 | 0.929141 | 98,86,71 | 98,85,71 | `invert(98%) sepia(23%) saturate(14403%) hue-rotate(306deg) brightness(31%) contrast(61%)` |
| 154 | `#301d0e` | 0.9325 | 0.4330 | 0.85471 | 0.854705 | 48,29,14 | 48,30,14 | `invert(67%) sepia(57%) saturate(6297%) hue-rotate(0deg) brightness(15%) contrast(89%)` |
| 155 | `#233344` | 0.9320 | 0.4357 | 0.94023 | 0.940232 | 35,51,68 | 35,50,68 | `invert(62%) sepia(89%) saturate(6611%) hue-rotate(200deg) brightness(18%) contrast(73%)` |
| 156 | `#052033` | 0.9318 | 0.4798 | 0.88209 | 0.882093 | 5,32,51 | 5,33,51 | `invert(21%) sepia(1%) saturate(10744%) hue-rotate(161deg) brightness(118%) contrast(155%)` |
| 157 | `#0d2536` | 0.9312 | 0.4814 | 0.88186 | 0.881857 | 13,37,54 | 13,38,54 | `invert(65%) sepia(14%) saturate(23452%) hue-rotate(180deg) brightness(18%) contrast(90%)` |
| 158 | `#402f1f` | 0.9302 | 0.4635 | 0.86988 | 0.869884 | 64,47,31 | 64,48,31 | `invert(5%) sepia(10%) saturate(2646%) hue-rotate(349deg) brightness(269%) contrast(84%)` |
| 159 | `#414c59` | 0.9301 | 0.5018 | 0.96809 | 0.968089 | 65,76,89 | 65,77,89 | `invert(41%) sepia(46%) saturate(8917%) hue-rotate(200deg) brightness(20%) contrast(49%)` |
| 160 | `#1e303b` | 0.9299 | 0.4931 | 0.99043 | 0.990433 | 30,48,59 | 30,49,59 | `invert(80%) sepia(15%) saturate(20589%) hue-rotate(173deg) brightness(16%) contrast(79%)` |
| 161 | `#14263a` | 0.9296 | 0.5398 | 0.96532 | 0.965323 | 20,38,58 | 20,39,58 | `invert(3%) sepia(26%) saturate(2431%) hue-rotate(180deg) brightness(291%) contrast(89%)` |
| 162 | `#1e1900` | 0.9296 | 0.4614 | 0.92952 | 0.929517 | 30,25,0 | 30,26,0 | `invert(94%) sepia(7%) saturate(19333%) hue-rotate(5deg) brightness(15%) contrast(106%)` |
| 163 | `#072230` | 0.9294 | 0.5069 | 0.95780 | 0.957803 | 7,34,48 | 7,35,48 | `invert(29%) sepia(3%) saturate(6305%) hue-rotate(155deg) brightness(58%) contrast(116%)` |
| 164 | `#1a2e3e` | 0.9294 | 0.4278 | 0.94016 | 0.940162 | 26,46,62 | 26,45,62 | `invert(56%) sepia(12%) saturate(16685%) hue-rotate(186deg) brightness(19%) contrast(83%)` |
| 165 | `#635c4e` | 0.9294 | 0.4684 | 0.91963 | 0.919634 | 99,92,78 | 99,91,78 | `invert(10%) sepia(1%) saturate(11988%) hue-rotate(360deg) brightness(272%) contrast(61%)` |
| 166 | `#0e2035` | 0.9293 | 0.4330 | 0.83896 | 0.838956 | 14,32,53 | 14,33,53 | `invert(76%) sepia(51%) saturate(13830%) hue-rotate(202deg) brightness(19%) contrast(89%)` |
| 167 | `#011f2a` | 0.9290 | 0.3463 | 0.92899 | 0.928989 | 1,31,42 | 1,30,42 | `invert(69%) sepia(5%) saturate(14795%) hue-rotate(163deg) brightness(18%) contrast(105%)` |
| 168 | `#2b3a49` | 0.9282 | 0.5442 | 0.97870 | 0.978699 | 43,58,73 | 43,59,73 | `invert(3%) sepia(15%) saturate(5778%) hue-rotate(185deg) brightness(263%) contrast(68%)` |
| 169 | `#30240d` | 0.9282 | 0.4800 | 0.93648 | 0.936482 | 48,36,13 | 48,35,13 | `invert(41%) sepia(5%) saturate(6823%) hue-rotate(360deg) brightness(26%) contrast(91%)` |
| 170 | `#021f2c` | 0.9277 | 0.5782 | 0.93314 | 0.933143 | 2,31,44 | 2,32,44 | `invert(79%) sepia(89%) saturate(11434%) hue-rotate(168deg) brightness(24%) contrast(126%)` |
| 171 | `#0e2636` | 0.9276 | 0.5757 | 0.98223 | 0.982234 | 14,38,54 | 14,39,54 | `invert(23%) sepia(3%) saturate(29803%) hue-rotate(178deg) brightness(35%) contrast(89%)` |
| 172 | `#3b291a` | 0.9273 | 0.5933 | 0.98434 | 0.984335 | 59,41,26 | 59,42,26 | `invert(5%) sepia(3%) saturate(21019%) hue-rotate(358deg) brightness(173%) contrast(80%)` |
| 173 | `#2c190a` | 0.9271 | 0.4828 | 0.93077 | 0.930773 | 44,25,10 | 44,24,10 | `invert(61%) sepia(1%) saturate(10417%) hue-rotate(343deg) brightness(35%) contrast(137%)` |
| 174 | `#07232e` | 0.9268 | 0.3393 | 0.95441 | 0.954411 | 7,35,46 | 7,34,46 | `invert(75%) sepia(23%) saturate(214%) hue-rotate(152deg) brightness(42%) contrast(227%)` |
| 175 | `#0a2434` | 0.9268 | 0.5613 | 0.97142 | 0.971419 | 10,36,52 | 10,37,52 | `invert(6%) sepia(42%) saturate(1467%) hue-rotate(167deg) brightness(149%) contrast(94%)` |
| 176 | `#0f2438` | 0.9267 | 0.5265 | 0.90408 | 0.904077 | 15,36,56 | 15,37,56 | `invert(100%) sepia(55%) saturate(2588%) hue-rotate(174deg) brightness(37%) contrast(216%)` |
| 177 | `#062332` | 0.9261 | 0.4811 | 0.95807 | 0.958072 | 6,35,50 | 6,34,50 | `invert(13%) sepia(4%) saturate(2718%) hue-rotate(157deg) brightness(186%) contrast(150%)` |
| 178 | `#001e31` | 0.9253 | 0.5639 | 0.84368 | 0.843677 | 0,30,49 | 0,29,49 | `invert(3%) sepia(63%) saturate(7009%) hue-rotate(179deg) brightness(292%) contrast(183%)` |
| 179 | `#042232` | 0.9249 | 0.4925 | 0.82416 | 0.824158 | 4,34,50 | 4,33,50 | `invert(78%) sepia(91%) saturate(17862%) hue-rotate(173deg) brightness(19%) contrast(98%)` |
| 180 | `#2f250e` | 0.9245 | 0.4344 | 0.93886 | 0.938864 | 47,37,14 | 47,36,14 | `invert(51%) sepia(67%) saturate(9259%) hue-rotate(47deg) brightness(27%) contrast(89%)` |
| 181 | `#243345` | 0.9245 | 0.5341 | 0.95853 | 0.958535 | 36,51,69 | 36,50,69 | `invert(42%) sepia(2%) saturate(1634%) hue-rotate(174deg) brightness(89%) contrast(248%)` |
| 182 | `#0c2632` | 0.9242 | 0.5352 | 0.94103 | 0.941032 | 12,38,50 | 12,37,50 | `invert(35%) sepia(77%) saturate(774%) hue-rotate(162deg) brightness(23%) contrast(92%)` |
| 183 | `#48362c` | 0.9238 | 0.5178 | 0.96806 | 0.968059 | 72,54,44 | 72,55,44 | `invert(59%) sepia(1%) saturate(6979%) hue-rotate(339deg) brightness(48%) contrast(127%)` |
| 184 | `#011c31` | 0.9236 | 0.4384 | 0.92600 | 0.926001 | 1,28,49 | 1,29,49 | `invert(60%) sepia(40%) saturate(5083%) hue-rotate(181deg) brightness(21%) contrast(106%)` |
| 185 | `#3d4958` | 0.9235 | 0.5169 | 0.96626 | 0.966265 | 61,73,88 | 61,72,88 | `invert(18%) sepia(34%) saturate(98%) hue-rotate(175deg) brightness(203%) contrast(205%)` |
| 186 | `#0e2438` | 0.9233 | 0.5375 | 0.96383 | 0.963833 | 14,36,56 | 14,37,56 | `invert(35%) sepia(35%) saturate(10329%) hue-rotate(194deg) brightness(21%) contrast(89%)` |
| 187 | `#06192f` | 0.9232 | 0.4309 | 0.80868 | 0.808680 | 6,25,47 | 6,26,47 | `invert(8%) sepia(45%) saturate(868%) hue-rotate(171deg) brightness(116%) contrast(103%)` |
| 188 | `#03192e` | 0.9226 | 0.4616 | 0.96877 | 0.968773 | 3,25,46 | 3,24,46 | `invert(67%) sepia(2%) saturate(8696%) hue-rotate(169deg) brightness(26%) contrast(128%)` |
| 189 | `#0f1625` | 0.9219 | 0.5297 | 0.99748 | 0.997478 | 15,22,37 | 15,21,37 | `invert(30%) sepia(14%) saturate(13097%) hue-rotate(218deg) brightness(11%) contrast(91%)` |
| 190 | `#233545` | 0.9218 | 0.4606 | 0.96876 | 0.968762 | 35,53,69 | 35,52,69 | `invert(75%) sepia(8%) saturate(29249%) hue-rotate(185deg) brightness(22%) contrast(82%)` |
| 191 | `#2f2917` | 0.9217 | 0.5214 | 0.99749 | 0.997488 | 47,41,23 | 47,42,23 | `invert(24%) sepia(12%) saturate(481%) hue-rotate(9deg) brightness(114%) contrast(154%)` |
| 192 | `#241201` | 0.9210 | 0.5023 | 0.96184 | 0.961839 | 36,18,1 | 36,19,1 | `invert(9%) sepia(16%) saturate(3321%) hue-rotate(356deg) brightness(86%) contrast(100%)` |
| 193 | `#3a2e1a` | 0.9209 | 0.5153 | 0.93418 | 0.934185 | 58,46,26 | 58,47,26 | `invert(9%) sepia(7%) saturate(3007%) hue-rotate(0deg) brightness(174%) contrast(92%)` |
| 194 | `#263840` | 0.9204 | 0.4922 | 0.91212 | 0.912115 | 38,56,64 | 38,55,64 | `invert(39%) sepia(59%) saturate(405%) hue-rotate(155deg) brightness(31%) contrast(81%)` |
| 195 | `#041e33` | 0.9200 | 0.5921 | 0.93167 | 0.931667 | 4,30,51 | 4,31,51 | `invert(9%) sepia(9%) saturate(7205%) hue-rotate(175deg) brightness(107%) contrast(100%)` |
| 196 | `#67594a` | 0.9196 | 0.4184 | 0.96002 | 0.960017 | 103,89,74 | 103,88,74 | `invert(9%) sepia(85%) saturate(862%) hue-rotate(360deg) brightness(138%) contrast(42%)` |
| 197 | `#575457` | 0.9187 | 0.4805 | 0.94426 | 0.944263 | 87,84,87 | 87,83,87 | `invert(33%) sepia(2%) saturate(2966%) hue-rotate(251deg) brightness(47%) contrast(49%)` |
| 198 | `#66574c` | 0.9185 | 0.4955 | 0.97579 | 0.975790 | 102,87,76 | 102,86,76 | `invert(17%) sepia(4%) saturate(14293%) hue-rotate(350deg) brightness(79%) contrast(42%)` |
| 199 | `#1a2b3f` | 0.9184 | 0.5690 | 0.94757 | 0.947568 | 26,43,63 | 26,44,63 | `invert(3%) sepia(23%) saturate(5162%) hue-rotate(195deg) brightness(227%) contrast(81%)` |
| 200 | `#0d2237` | 0.9182 | 0.3559 | 0.99177 | 0.991775 | 13,34,55 | 13,35,55 | `invert(61%) sepia(53%) saturate(2236%) hue-rotate(184deg) brightness(23%) contrast(105%)` |

These are all 200 retained worst colors; the JSON's `worst[]` adds the per-row target L* and machine-readable fields.

## Hardness cross-check

`loss` is the mixed RGB+HSL rendered metric of the covering claim. Colors whose loss sits just under the threshold (>= 0.99) are the near-threshold population that burned search escalation rounds: the same survivors the hardness map artifact is built from. Mean Delta-E2000 per loss band and the overlap of the worst Delta-E population with the near-threshold band test whether colorimetric difficulty and search difficulty share a cause:

| loss band | rows | mean Delta-E2000 | max Delta-E2000 | at | mean target L* |
| --------- | ---- | ---------------- | --------------- | -- | -------------- |
| 0.00 <= loss < 0.50 | 1,547,072 | 0.000000 | 0.000000 | `#000000` | 56.4 |
| 0.50 <= loss < 0.90 | 9,231,796 | 0.019395 | 1.077481 | `#221a08` | 57.2 |
| 0.90 <= loss < 0.99 | 5,270,344 | 0.048215 | 1.076958 | `#211501` | 58.2 |
| 0.99 <= loss < 1.00 | 728,004 | 0.053472 | 1.095415 | `#231a0b` | 58.7 |
| loss >= 1 (gate violation) | 0 | - | - | `-` | - |

Near-threshold band (`0.99 <= loss < 1.00`): 728,004 rows (4.3392% of all).

- overlap with the worst 50 Delta-E colors: 4 of them in the band (chance: 2.2, enrichment x1.8)
- overlap with the worst 100 Delta-E colors: 12 of them in the band (chance: 4.3, enrichment x2.8)
- overlap with the worst 200 Delta-E colors: 23 of them in the band (chance: 8.7, enrichment x2.7)
- mean recomputed loss of the worst 200 Delta-E colors: 0.93429 (overall mean recomputed loss: 0.78804).

Clustering (mean target L*, D65): worst-200 Delta-E population 14.9; near-threshold band 58.7; whole cube 57.5.

This section reports cross-check numbers only. What they mean is prose, not code: it lives in README.md and the writeup and must be re-checked against each regenerated snapshot. The loss-band population is a proxy: the survivor-based hardness map supersedes it. Rerun `scan` when it lands.

## Method and runtime

- sRGB -> CIELAB (D65): IEC 61966-2-1 inverse gamma + matrix, reference white (0.95047, 1.0, 1.08883). CIEDE2000 exactly as published by Sharma, Wu & Dalley (2005), kL = kC = kH = 1. All 34 Table I pairs are reproduced to 4-decimal rounding by `selftest`. Cross-validated against the independent `coloraide` implementation (`crosscheck_coloraide.py`). Every published worst-row value can also be recomputed without this tool's colorimetry at all via `recheck_rows_coloraide.py` (optional dev deps).

- Each row: witness parsed and rendered by the verifier's `parse_chain`/`render_chain`, loss recomputed by its `rendered_loss` with `verify_row`-identical status semantics (proved by selftest), then CIELAB + CIEDE2000 for the quantized and float renderings.

- Quantized rendering uses round() to 8-bit codes. Exact-half ties, if a witness has one, can flip one code value across platforms inside the verifier's browser-golden tolerance (1.0/255). The float columns quantify the per-snapshot magnitude.

- Runtime: 41.4 s over all 16,777,216 rows with 12 job(s) on Darwin 24.6.0 (arm64) (12 CPUs), Python CPython 3.9.4. Streaming `SELECT ... WHERE id BETWEEN ? AND ?` over contiguous id ranges (the verifier's scan shape). Cost is transcendental-bound at about 20 math calls per row (9 cbrt, 4 atan2, plus the CIEDE2000 trig) and scales linearly in jobs.

- Machine-readable stats: `de2000_stats.json` (histogram edges/counts, bands, worst colors, method, checksum). This Markdown file and the JSON are both produced by one `scan` run from the artifact alone. Runtime and timestamp are the only run-dependent fields. Averages are stored rounded to 10+ decimals, so the numbers are byte-stable across job counts: float summation noise stays below the rounding.

License: MIT (tooling), matching the library; dataset CC-BY-4.0.
