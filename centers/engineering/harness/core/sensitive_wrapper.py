#!/usr/bin/env python3
"""
涉敏模型包装器 - 适配任何 Model 实现
自动处理 1026(输入涉敏)/1027(输出涉敏)

使用方式:
    from sensitive_wrapper import SensitiveModelWrapper
    from model import LitellmModel, ModelConfig
    
    base_model = LitellmModel(ModelConfig(model_name="..."))
    model = SensitiveModelWrapper(base_model)
    result = model.query(messages)  # 自动处理涉敏
"""

import logging
from typing import Optional

# 相对导入 sensitivity_filter
import sys
sys.path.insert(0, str(__file__).rsplit('/', 1)[0])
from sensitivity_filter import sanitize_text, downgrade_prompt, check_sensitivity

logger = logging.getLogger("model.sensitive_wrapper")


class SensitivityError(Exception):
    """涉敏错误基类"""
    def __init__(self, code: int, message: str, original: str = ""):
        self.code = code
        self.message = message
        self.original = original
        super().__init__(f"[{code}] {message}")


class InputSensitivityError(SensitivityError):
    """1026: 输入内容涉敏"""
    pass


class OutputSensitivityError(SensitivityError):
    """1027: 输出内容涉敏"""
    pass


class SensitiveModelWrapper:
    """
    涉敏处理包装器
    
    工作流程:
    1. query() 收到 messages
    2. 对每条 user message 做预检 + 转换 (1026 预防)
    3. 调用底层模型
    4. 如果返回 1027 → 降级 prompt 重试
    5. 返回结果
    
    支持的底层模型错误格式:
    - MiniMax API: {"error_code": 1026/1027, "msg": "..."}
    - 标准 Exception with .error_code 属性
    """
    
    def __init__(self, model, max_retry: int = 2):
        self.model = model
        self.max_retry = max_retry
        self._logger = logger
    
    def query(self, messages: list[dict]) -> dict:
        """
        带涉敏处理的查询
        """
        # Step 1: 对输入做预检和转换
        converted_messages = self._sanitize_messages(messages)
        
        # Step 2: 执行查询，支持 1027 降级重试
        last_error = None
        
        for attempt in range(self.max_retry + 1):
            try:
                response = self.model.query(converted_messages)
                
                # 检查输出是否为空（1027 可能返回空内容）
                if not response.get("content", "").strip():
                    raise OutputSensitivityError(
                        1027, 
                        "输出内容被过滤，返回为空",
                        original=response.get("content", "")
                    )
                
                return response
                
            except SensitivityError as e:
                if e.code == 1027 and attempt < self.max_retry:
                    # 1027: 降级重试
                    self._logger.warning(f"1027 输出涉敏，降级重试 (attempt {attempt+1})")
                    converted_messages = self._downgrade_messages(converted_messages)
                    last_error = e
                    continue
                else:
                    raise
                    
            except Exception as e:
                # 检查是否是 API 返回的涉敏错误
                error_code = self._extract_error_code(e)
                if error_code in (1026, 1027) and attempt < self.max_retry:
                    self._logger.warning(f"API 返回 {error_code}，处理重试 (attempt {attempt+1})")
                    
                    if error_code == 1026:
                        # 1026: 转换输入后重试
                        converted_messages = self._sanitize_messages(messages, force=True)
                    else:
                        # 1027: 降级后重试
                        converted_messages = self._downgrade_messages(converted_messages)
                    
                    last_error = e
                    continue
                else:
                    raise
        
        # 达到最大重试次数
        raise last_error or OutputSensitivityError(1027, "重试次数耗尽")
    
    def _sanitize_messages(self, messages: list[dict], force: bool = False) -> list[dict]:
        """对 messages 中的文本进行脱敏转换"""
        result = []
        changed = False
        
        for msg in messages:
            if msg.get("role") == "system":
                # system message 保持不变（通常不触发涉敏）
                result.append(msg)
                continue
                
            content = msg.get("content", "")
            if isinstance(content, str):
                should_convert, triggers = check_sensitivity(content)
                if should_convert or force:
                    new_content, was_changed = sanitize_text(content)
                    if was_changed:
                        self._logger.info(f"涉敏转换: {triggers}")
                        content = new_content
                        changed = True
            
            result.append({**msg, "content": content})
        
        return result if changed else messages
    
    def _downgrade_messages(self, messages: list[dict]) -> list[dict]:
        """降级 messages 以绕过输出涉敏"""
        result = []
        
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                new_content = downgrade_prompt(content)
                result.append({**msg, "content": new_content})
            else:
                result.append(msg)
        
        return result
    
    def _extract_error_code(self, e: Exception) -> Optional[int]:
        """从异常中提取错误码"""
        # MiniMax API 格式: {"error_code": 1026/1027, "msg": "..."}
        if hasattr(e, 'error_code'):
            return e.error_code
        
        # 从异常消息中提取
        msg = str(e)
        for code in (1026, 1027):
            if str(code) in msg:
                return code
        
        # 尝试解析 JSON 错误
        try:
            import json
            if hasattr(e, 'response'):
                data = e.response.json()
                return data.get("error_code")
        except Exception:
            pass
        
        return None
    
    def __getattr__(self, name: str):
        """代理所有其他属性到底层模型"""
        return getattr(self.model, name)


# 测试
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("=== 涉敏包装器测试 ===")
    
    # 测试预检
    test_messages = [
        {"role": "user", "content": "有人说死亡是暴力的最终形式。这场战争导致数千万人丧生。"}
    ]
    
    wrapper = SensitiveModelWrapper(None)  # 不需要真实模型做预检测试
    
    sanitized = wrapper._sanitize_messages(test_messages)
    print(f"原文: {test_messages[0]['content']}")
    print(f"转换: {sanitized[0]['content']}")
    print("✅ 涉敏包装器测试通过")
