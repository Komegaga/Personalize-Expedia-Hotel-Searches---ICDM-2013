#!/usr/bin/env python
# -*- coding: utf-8 -*-
import math
from time import time
import numpy as np
from pyspark import SparkConf, SparkContext
from pyspark.mllib.classification import LogisticRegressionWithLBFGS, LogisticRegressionModel
from pyspark.mllib.tree import DecisionTree
from pyspark.mllib.regression import LabeledPoint
from pyspark.mllib.evaluation import RegressionMetrics
from pyspark.mllib.evaluation import BinaryClassificationMetrics
from pyspark.mllib.util import MLUtils


def SetLogger(sc):
    logger = sc._jvm.org.apache.log4j
    logger.LogManager.getLogger("org"). setLevel(logger.Level.ERROR)
    logger.LogManager.getLogger("akka").setLevel(logger.Level.ERROR)
    logger.LogManager.getRootLogger().setLevel(logger.Level.ERROR)

def SetPath(sc):
    global Path
    if sc.master[0:5]=="local" :
        Path="/home/cs/Downloads/"
    else:   
        Path="hdfs://master:9000/data/"

def extract_label(record):
    label = record[-1]
    return float(label)


def convert_float(x):
    return 0 if x == "NULL" else float(x)


def extract_features(record):
    """index = np.arange(51)
    features_index = index[3:51]"""
    features_index = [4,6,8,9,10,11,12,13,14,16,18,19,20,21,22,24,26,30,33,35,38,39,41,44,45,47]
    features = [convert_float(record[x]) for x in features_index]
    return np.asarray(features)



def prepare_data(sc):
    print("開始匯入資料...")
    rawDataWithHeader = sc.textFile("s3n://bigdata17demo/data_half_0.csv")
    header = rawDataWithHeader.first()
    rawData = rawDataWithHeader.filter(lambda x: x != header)
    lines = rawData.map(lambda x: x.split(","))
    print (lines.first())
    print("共計：" + str(lines.count()) + "筆")
    labelpointRDD = lines.map(lambda r: LabeledPoint(extract_label(r), extract_features(r)))
    print (labelpointRDD.first())
    (trainData, validationData) = labelpointRDD.randomSplit([8, 2])
    print("將資料分trainData:" + str(trainData.count()) +
          "validationData:" + str(validationData.count()))

    return (trainData, validationData)

def parsePoint(line):
    values = [float(x) for x in line.split(' ')]
    return LabeledPoint(values[0], values[1:])

def CreateSparkContext():
    sparkConf = SparkConf()   \
        .setAppName("RunDecisionTreeClassficaiton") \
        .set("spark.ui.showConsoleProgress", "false")
    sc = SparkContext(conf=sparkConf)
    print ("master=" + sc.master)
    SetLogger(sc)
    return (sc)


def trainEvaluateModel(trainData):
    model = LogisticRegressionWithLBFGS.train(trainData,intercept = True)
    return model


def evaluateModel(model, validationData):
    score = model.predict(validationData.map(lambda p: p.features))
    '''labelsAndPredictions = validationData.map(lambda p: p.label).zip(score)'''
    labelsAndPreds = validationData.map(lambda p: (p.label, float(model.predict(p.features))))
    metrics = BinaryClassificationMetrics(labelsAndPreds)
    print("Area under PR = %s" % metrics.areaUnderPR)
    print("Area under ROC = %s" % metrics.areaUnderROC)
    testErr = labelsAndPreds.filter(lambda seq: seq[0] != seq[1]).count() / float(validationData.count())
    print('Test Error = ' + str(testErr))
''' print('Learned classification tree model:')
    print(model.toDebugString()) '''




def predictData(sc, model):
    #----------------------1.匯入並轉換資料-------------
    print("開始匯入資料...")
    rawDataWithHeader = sc.textFile("s3n://bigdata17demo/train.csv")
    header = rawDataWithHeader.first()
    rawData = rawDataWithHeader.filter(lambda x:x !=header)
    lines = rawData.map(lambda x: x.split(","))
    print("共計：" + str(lines.count()) + "筆")
    #----------------------2.建立訓練評估所需資料 LabeledPoint RDD-------------
    labelpointRDD = lines.map(lambda r: LabeledPoint(extract_label(r), extract_features(r)))
    print (labelpointRDD.first())
    testData = labelpointRDD
    print("testData:" + str(testData.count()))
    labelsAndPreds = testData.map(lambda p: (p.label, float(model.predict(p.features))))
    metrics = BinaryClassificationMetrics(labelsAndPreds)
    print("Area under PR = %s" % metrics.areaUnderPR)
    print("Area under ROC = %s" % metrics.areaUnderROC)
    testErr = labelsAndPreds.filter(lambda seq: seq[0] != seq[1]).count() / float(testData.count())
    print('Test Error = ' + str(testErr))
    #----------------------4.進行預測並顯示結果--------------

    # 把預測結果寫出來
    f = open('workfile', 'w')
    for lp in labelpointRDD.take(499999):
        predict = int(model.predict(lp.features))
        dataDesc = "  " + str(predict) + " "
        f.write(dataDesc)
    f.close()


if __name__ == "__main__":
    sc = CreateSparkContext()
    (trainData, validationData) = prepare_data(sc)
    trainData.persist()
    validationData.persist()
    model = trainEvaluateModel(trainData)
    model.setThreshold(0.3)
    #model.save(sc)
    evaluateModel(model, validationData)
    print(model.threshold)
    print('截距 = ' + str(model.intercept))
    print('係數 = ' + str(model.weights))
    print('特徵數 = ' + str(model.numFeatures))
    predictData(sc, model)
