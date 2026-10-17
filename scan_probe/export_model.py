"""Card-scan probe: export two small image models (torchvision's MobileNetV3
small and large, ImageNet weights, BSD licence) to ONNX, cut after the
average pool so they output one feature vector per picture. ONNX is what a
phone browser can run (onnxruntime-web), so the probe measures exactly what
the site would run.

  python scan_probe/export_model.py --out OUT/models
"""
import argparse
import os

import torch
import torchvision


class Features(torch.nn.Module):
    def __init__(self, net):
        super().__init__()
        self.features = net.features
        self.pool = net.avgpool

    def forward(self, x):
        return torch.flatten(self.pool(self.features(x)), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    nets = {
        "mnv3s": torchvision.models.mobilenet_v3_small(weights="DEFAULT"),
        "mnv3l": torchvision.models.mobilenet_v3_large(weights="DEFAULT"),
    }
    for name, net in nets.items():
        model = Features(net).eval()
        x = torch.zeros(1, 3, 224, 224)
        path = os.path.join(args.out, name + ".onnx")
        try:
            torch.onnx.export(model, x, path, input_names=["x"], output_names=["y"],
                              dynamic_axes={"x": {0: "n"}, "y": {0: "n"}}, opset_version=17, dynamo=False)
        except Exception as ex:  # noqa: BLE001 - newer torch: only the dynamo exporter
            print("classic export failed, trying dynamo:", ex)
            torch.onnx.export(model, (x,), path, input_names=["x"], output_names=["y"],
                              dynamic_shapes={"x": {0: torch.export.Dim("n", min=1, max=256)}},
                              opset_version=18, dynamo=True, external_data=False)
        # check the ONNX file gives the same numbers as torch, for a batch of two
        import numpy as np
        import onnxruntime as ort
        xb = torch.randn(2, 3, 224, 224)
        want = model(xb).detach().numpy()
        got = ort.InferenceSession(path, providers=["CPUExecutionProvider"]).run(None, {"x": xb.numpy()})[0]
        print(name, os.path.getsize(path) // 1024, "KB", want.shape, "max difference", float(np.abs(want - got).max()))


if __name__ == "__main__":
    main()
