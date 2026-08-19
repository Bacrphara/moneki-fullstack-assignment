# 演示脚本（约 2 分钟）

## 1. 看板与数据质量

1. 执行 `python manage.py import_sales`，展示重复执行会跳过同一 SHA-256 批次。
2. 打开首页，说明默认显示数据最新 30 天。
3. 切换日期，观察营业额、订单数、客单价、趋势图和 Top 10 同步刷新。
4. 展示“今日经营雷达”的近期高点和领先门店。

## 2. 三个可信问题

### 问题一：哪个品类的门店营业额最高？

真实全量结果：**日料，¥87,292.00**。证据来自 `Sale → Store` JOIN 后按 `store.category` 聚合。

### 问题二：牛肉poke六月卖了多少钱？

真实结果：**¥13,314.00，180 个去重订单**。证据来自 `Sale → Product` JOIN，筛选商品名和 2026-06。

独立核验：

```bash
python manage.py shell -c "from analytics.models import Sale; from django.db.models import Sum; print(Sale.objects.filter(product__name='牛肉poke',date__year=2026,date__month=6).aggregate(Sum('amount')))"
```

### 问题三：客单价最近是涨了还是跌了？

系统比较数据中的最新两个完整自然月，同时展示两期客单价和变化值；展开“数据依据”查看工具和区间。

## 3. 追问、联动与拒答

1. 在商品问题后追问“那五月呢？”，展示 SQLite 会话继承商品语境并切换月份。
2. 点击“同步到看板”，日期筛选与图表随证据区间更新。
3. 问“明天会下雨吗？”，系统说明数据集不包含天气，而不是编造答案。
4. 断开模型网络后再次提问，页面标记“本地可靠解析”，数据库数字仍保持一致。

## 4. 自动化证明

```bash
python manage.py test
```

重点展示：答案数字契约、脏数据审计、非法工具拒绝和网络重试降级测试。
