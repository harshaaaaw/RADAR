import os
import torch
import torchvision.models as models
from ultralytics import YOLO

class MobileNetFeatureExtractor(torch.nn.Module):
    def __init__(self, base_model):
        super().__init__()
        self.features = base_model.features
        
    def forward(self, x):
        x = self.features(x)
        x = torch.nn.functional.adaptive_avg_pool2d(x, 1)
        x = torch.flatten(x, 1)
        return x

def main():
    # Create models directory if not exists
    os.makedirs("models", exist_ok=True)
    print("Created models/ directory.")

    # 1. Export YOLOv8 to ONNX
    print("Loading and exporting YOLOv8 model to ONNX...")
    if os.path.exists("yolov8n.pt"):
        yolo_model = YOLO("yolov8n.pt")
        # Export with opset 12 for maximum OpenCV compatibility
        yolo_model.export(format="onnx", imgsz=[640, 640], opset=12)
        # Move the exported file to models/yolov8n.onnx or similar
        exported_path = "yolov8n.onnx"
        if os.path.exists(exported_path):
            target_path = os.path.join("models", "yolov8_layout.onnx")
            if os.path.exists(target_path):
                os.remove(target_path)
            os.rename(exported_path, target_path)
            print(f"Successfully exported YOLOv8 to {target_path}")
        else:
            print("YOLO export finished but yolov8n.onnx not found in root.")
    else:
        print("yolov8n.pt not found in root directory!")

    # 2. Export MobileNetV3 feature extractor to ONNX
    print("Loading and exporting MobileNetV3 feature extractor to ONNX...")
    try:
        base_mobilenet = models.mobilenet_v3_small(pretrained=True)
        mobilenet_extractor = MobileNetFeatureExtractor(base_mobilenet)
        mobilenet_extractor.eval()
        dummy_input = torch.randn(1, 3, 224, 224)
        target_path = os.path.join("models", "mobilenetv3.onnx")
        
        # Force legacy tracing (dynamo=False) to get a clean ONNX graph for OpenCV DNN
        torch.onnx.export(
            mobilenet_extractor, 
            dummy_input, 
            target_path, 
            export_params=True,
            opset_version=12,
            do_constant_folding=True,
            input_names=["input"],
            output_names=["output"],
            dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
            dynamo=False
        )
        print(f"Successfully exported MobileNetV3 to {target_path}")
    except Exception as exc:
        print(f"Failed to export MobileNetV3 to ONNX: {exc}")

if __name__ == "__main__":
    main()
