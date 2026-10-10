# Third-party components

The application code is AGPL-3.0-only. It uses PyMuPDF (AGPL-3.0), PySide6/Qt (LGPL/GPL/commercial licensing options; distributed here under LGPL where available), MLX and mlx-lm (MIT), Hugging Face transformers (Apache-2.0), and document parsing libraries under their respective licenses.

`prepare_build.py` collects license/notice files from the exact installed distributions into `Contents/Resources/Licenses`. Corresponding application source and build scripts are shipped in `Contents/Resources/Source`. The dependency versions are recorded in `requirements-lock.txt` inside the source bundle. Libraries are dynamically linked. The build scripts permit rebuilding the application with modified libraries; the local signature does not require a private Developer ID key.

Model weights are not redistributed with the app. Each catalog entry links to its upstream model card and license. Gemma's terms are separate from this project's AGPL license.

This project is not affiliated with Apple, Alibaba/Qwen, Google or Hugging Face.
