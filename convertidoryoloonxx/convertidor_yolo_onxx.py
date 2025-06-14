from ultralytics import YOLO

model = YOLO("yolo11n.pt")
model.export(format="onnx", simplify=True, dynamic=False, opset=11)
print("Modelo convertido a: yolo11n.onnx")