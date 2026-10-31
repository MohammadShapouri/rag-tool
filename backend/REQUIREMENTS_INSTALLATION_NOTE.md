### Docker / Linux Installation Tip for PyTorch
If building inside Docker without a GPU, install the CPU-only wheel of PyTorch first to reduce container image size:

```bash
pip install torch --extra-index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```