"""
Google 账户数据模型
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, JSON
from sqlalchemy.sql import func
from app.models.database import Base


class GoogleAccount(Base):
    """Google 账户表"""
    __tablename__ = "google_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, comment="Google邮箱")
    display_name = Column(String(255), default="", comment="显示名称")
    
    # Cookie 数据（核心鉴权）
    cookies_json = Column(Text, nullable=False, comment="完整Cookie JSON字符串")
    
    # 关键 Token
    mstk = Column(Text, default="", comment="主鉴权令牌")
    stkp = Column(Text, default="", comment="会话追踪参数")
    ei = Column(String(255), default="", comment="最近一次Event ID")
    elrc = Column(Text, default="", comment="对话上下文令牌")
    sca_esv = Column(String(255), default="", comment="客户端环境签名")
    
    # XSRF / Anti-CSRF
    xsrf_token = Column(Text, default="", comment="XSRF Token")
    at_token = Column(Text, default="", comment="Anti-CSRF Token (batchexecute)")
    
    # 状态
    is_active = Column(Boolean, default=True, comment="是否启用")
    status = Column(String(50), default="idle", comment="当前状态: idle/busy/error/disabled")
    error_message = Column(Text, default="", comment="最近错误信息")
    
    # 统计
    total_requests = Column(Integer, default=0, comment="总请求数")
    success_requests = Column(Integer, default=0, comment="成功请求数")
    fail_requests = Column(Integer, default=0, comment="失败请求数")
    last_used_at = Column(DateTime, nullable=True, comment="最后使用时间")
    
    # Cookie 轮换
    last_cookie_rotate_at = Column(DateTime, nullable=True, comment="最后Cookie轮换时间")
    cookie_rotate_count = Column(Integer, default=0, comment="Cookie轮换次数")
    
    # 优先级/权重（用于轮询策略）
    priority = Column(Integer, default=0, comment="优先级，越大越优先")
    weight = Column(Float, default=1.0, comment="权重")
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class RequestLog(Base):
    """请求日志表"""
    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 请求信息
    request_id = Column(String(64), unique=True, nullable=False, comment="请求唯一ID")
    account_id = Column(Integer, nullable=True, comment="使用的账户ID")
    account_email = Column(String(255), default="", comment="使用的账户邮箱")
    
    # OpenAI 请求参数
    model = Column(String(100), default="", comment="请求的模型名")
    messages_json = Column(Text, default="", comment="请求消息体JSON")
    stream = Column(Boolean, default=False, comment="是否流式")
    
    # 实际发送内容
    query_text = Column(Text, default="", comment="发送给Google的实际查询文本")
    
    # 响应
    response_text = Column(Text, default="", comment="AI返回的文本内容")
    prompt_tokens = Column(Integer, default=0, comment="输入token估算")
    completion_tokens = Column(Integer, default=0, comment="输出token估算")
    total_tokens = Column(Integer, default=0, comment="总token估算")
    
    # 状态
    status = Column(String(20), default="pending", comment="状态: pending/success/error")
    error_message = Column(Text, default="", comment="错误信息")
    
    # 耗时
    duration_ms = Column(Integer, default=0, comment="请求耗时(毫秒)")
    
    # 客户端信息
    client_ip = Column(String(50), default="", comment="客户端IP")
    api_key_used = Column(String(100), default="", comment="使用的API Key（脱敏）")
    
    # 时间
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class SystemConfig(Base):
    """系统配置表（键值对）"""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, nullable=False, comment="配置键")
    value = Column(Text, default="", comment="配置值")
    description = Column(String(500), default="", comment="配置说明")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ApiKey(Base):
    """API Key 管理表"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, nullable=False, comment="API Key")
    name = Column(String(255), default="", comment="备注名称")
    is_active = Column(Boolean, default=True, comment="是否启用")
    allowed_models = Column(Text, default="", comment="允许使用的模型ID列表(逗号分隔)，空=全部")
    total_requests = Column(Integer, default=0, comment="总请求数")
    max_requests = Column(Integer, nullable=True, comment="最大允许请求次数，NULL表示不限制")
    expires_at = Column(DateTime, nullable=True, comment="过期时间，NULL表示不过期")
    last_used_at = Column(DateTime, nullable=True, comment="最后使用时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class ModelConfig(Base):
    """模型配置表 - 管理可用的模型ID"""
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(String(100), unique=True, nullable=False, comment="模型ID，如 gemini-2.5-pro")
    model_name = Column(String(255), default="", comment="模型显示名称")
    description = Column(Text, default="", comment="模型描述")
    is_active = Column(Boolean, default=True, comment="是否启用")
    sort_order = Column(Integer, default=0, comment="排序（越大越靠前）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
