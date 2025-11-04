# file: backend/model_server.py
"""
Model server wrapper.

文档优先：ContractClassifierServer 封装模型加载、预测与热重载。
"""
import os
import sys
import threading
from typing import List, Optional, Tuple

import torch
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
from peft import PeftModel

# labels 直接从你提供的代码复用（可按需修改）
LABELS = [
    'Unhandled Exception (Unchecked Call Return Value): Failing to check the return value of external calls (e.g., send(), call()), which may cause unexpected behavior if the call fails.',
    'Authorization through tx.origin: Using tx.origin for authorization checks, which can be exploited by malicious contracts forwarding transactions.',
    'Reentrancy: Allowing an external contract to re-enter the function before state updates are completed, potentially draining funds.',
    'Arithmetic (Integer Overflow and Underflow): Lack of overflow/underflow checks in arithmetic operations, leading to incorrect results or exploits.',
    'Timestamp Ordering (Transaction Order Dependence): Logic depending on transaction order or block timestamp, which can be manipulated by miners.',
    'Locked Ether: Ether sent to a contract cannot be withdrawn because there is no withdrawal function or self-destruct.',
    'Time Manipulation (Block values as a proxy for time): Directly relying on block.timestamp or block.number as time sources, which miners can slightly alter.'
]

class ContractClassifierServer:
    """
    线程安全的模型包装器。支持 load_model、predict、reload_model。
    """
    def __init__(self, base_model_path: str, adapter_path: Optional[str] = None, device: Optional[str] = None):
        self.base_model_path = base_model_path
        self.adapter_path = adapter_path
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.lock = threading.RLock()
        self.model = None
        self.tokenizer = None
        self.loaded = False
        self.last_load_error = None
        # 延迟加载不在 __init__ 里直接触发，调用 load_model 启动加载
    def _local_files_only(self):
        # 在有些部署会希望从远程加载，现阶段强制本地加载
        return True

    def load_model(self, base_model_path: Optional[str] = None, adapter_path: Optional[str] = None):
        with self.lock:
            base_path = base_model_path or self.base_model_path
            adapter = adapter_path or self.adapter_path

            print(f"\n[🧠] 正在加载模型：")
            print(f"     ➤ Base model: {base_path}")
            print(f"     ➤ Adapter: {adapter or '(无)'}")
            print(f"     ➤ Device: {self.device}")

            try:
                # --- 1️⃣ 加载配置 ---
                config = AutoConfig.from_pretrained(
                    base_path,
                    num_labels=len(LABELS),
                    problem_type="multi_label_classification",
                    local_files_only=self._local_files_only()
                )

                # --- 2️⃣ 加载基础模型（不忽略维度不匹配）---
                base_model = AutoModelForSequenceClassification.from_pretrained(
                    base_path,
                    config=config,
                    local_files_only=self._local_files_only()
                )

                # --- 3️⃣ 加载 adapter（如果存在）---
                if adapter and os.path.isdir(adapter):
                    try:
                        model = PeftModel.from_pretrained(
                            base_model,
                            adapter,
                            local_files_only=self._local_files_only()
                        )
                        print("[✅] LoRA adapter 加载成功。")
                    except Exception as e:
                        print(f"[⚠️] Adapter 加载失败：{e}")
                        print("     ⚠️ 使用基础模型继续运行（未加载微调权重）。")
                        model = base_model
                else:
                    print("[ℹ️] 未提供 adapter 或路径不存在，使用基础模型。")
                    model = base_model

                # --- 4️⃣ 设置设备 ---
                model.to(self.device)
                model.eval()

                # --- 5️⃣ 加载 tokenizer ---
                tokenizer = AutoTokenizer.from_pretrained(base_path, local_files_only=self._local_files_only())
                if tokenizer.pad_token is None:
                    tokenizer.pad_token = tokenizer.eos_token

                # --- 6️⃣ 清理旧模型 ---
                try:
                    if getattr(self, "model", None) is not None:
                        del self.model
                        torch.cuda.empty_cache()
                except Exception:
                    pass

                # --- 7️⃣ 保存新模型 ---
                self.model = model
                self.tokenizer = tokenizer
                self.base_model_path = base_path
                self.adapter_path = adapter
                self.loaded = True
                self.last_load_error = None

                print("[✅] 模型加载完成！")
                return True, "loaded"

            except Exception as e:
                self.loaded = False
                self.last_load_error = str(e)
                print(f"[❌] 模型加载失败：{e}")
                return False, str(e)

            

    def predict(self, text: str, threshold: float = 0.5, max_length: int = 512) -> Tuple[List[str], List[float]]:
        """
        返回 (matched_labels, probs)
        """
        if not self.loaded:
            raise RuntimeError("Model not loaded: " + (self.last_load_error or "unknown"))
        with self.lock:
            # tokenize
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=max_length
            )
            # move inputs to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.sigmoid(logits).cpu().numpy()[0].tolist()
            matched = [LABELS[i] for i, p in enumerate(probs) if p >= threshold]
            return matched, probs

    def status(self):
        return {
            "loaded": self.loaded,
            "device": self.device,
            "base_model_path": self.base_model_path,
            "adapter_path": self.adapter_path,
            "last_load_error": self.last_load_error
        }
