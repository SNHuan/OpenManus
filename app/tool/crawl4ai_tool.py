"""
基于Crawl4AI的高效网页爬取工具
简单、快速、强大的网页内容获取解决方案
"""

import asyncio
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any
from pydantic import Field

from app.tool.base import BaseTool, ToolResult
from app.logger import logger


class Crawl4AIExecutor:
    """
    Crawl4AI 执行器 - 在独立线程中运行以避免事件循环冲突
    """

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="crawl4ai")
        self._setup_done = False

    def _setup_event_loop(self):
        """在执行线程中设置正确的事件循环策略"""
        if sys.platform == "win32" and not self._setup_done:
            try:
                # 在 Windows 下使用 ProactorEventLoopPolicy 支持子进程
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                logger.debug("Crawl4AI thread: ProactorEventLoopPolicy set")
            except Exception as e:
                logger.warning(f"Crawl4AI thread: Failed to set event loop policy: {e}")

            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._setup_done = True

        return asyncio.get_event_loop()

    def _run_crawl_single(self, url: str, config_dict: dict) -> dict:
        """在独立线程中执行单个URL爬取"""
        try:
            loop = self._setup_event_loop()

            async def _crawl():
                from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

                # 重建配置对象
                config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    word_count_threshold=config_dict.get('word_count_threshold', 10),
                    excluded_tags=config_dict.get('excluded_tags', []),
                    exclude_external_links=config_dict.get('exclude_external_links', True),
                    remove_overlay_elements=config_dict.get('remove_overlay_elements', True),
                    page_timeout=config_dict.get('page_timeout', 30000),
                    wait_for=config_dict.get('wait_for'),
                    verbose=False
                )

                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url=url, config=config)
                    return {
                        'success': result.success,
                        'url': result.url,
                        'markdown': result.markdown if result.success else '',
                        'cleaned_html': result.cleaned_html if result.success else '',
                        'error_message': result.error_message if not result.success else '',
                        'metadata': getattr(result, 'metadata', {}),
                        'response_time': getattr(result, 'response_time', 0)
                    }

            return loop.run_until_complete(_crawl())

        except Exception as e:
            logger.error(f"Crawl4AI single crawl error: {e}")
            return {
                'success': False,
                'url': url,
                'markdown': '',
                'cleaned_html': '',
                'error_message': str(e),
                'metadata': {},
                'response_time': 0
            }

    def _run_crawl_batch(self, urls: List[str], config_dict: dict) -> List[dict]:
        """在独立线程中执行批量爬取"""
        try:
            loop = self._setup_event_loop()

            async def _crawl_batch():
                from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

                config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    word_count_threshold=config_dict.get('word_count_threshold', 10),
                    excluded_tags=config_dict.get('excluded_tags', []),
                    exclude_external_links=config_dict.get('exclude_external_links', True),
                    remove_overlay_elements=config_dict.get('remove_overlay_elements', True),
                    page_timeout=config_dict.get('page_timeout', 30000),
                    wait_for=config_dict.get('wait_for'),
                    verbose=False
                )

                async with AsyncWebCrawler() as crawler:
                    results = await crawler.arun_many(urls, config=config)

                    processed_results = []
                    for result in results:
                        processed_results.append({
                            'success': result.success,
                            'url': result.url,
                            'markdown': result.markdown if result.success else '',
                            'cleaned_html': result.cleaned_html if result.success else '',
                            'error_message': result.error_message if not result.success else '',
                            'metadata': getattr(result, 'metadata', {}),
                            'response_time': getattr(result, 'response_time', 0)
                        })

                    return processed_results

            return loop.run_until_complete(_crawl_batch())

        except Exception as e:
            logger.error(f"Crawl4AI batch crawl error: {e}")
            return [{
                'success': False,
                'url': url,
                'markdown': '',
                'cleaned_html': '',
                'error_message': str(e),
                'metadata': {},
                'response_time': 0
            } for url in urls]

    async def crawl_single(self, url: str, config_dict: dict) -> dict:
        """异步执行单个URL爬取"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._run_crawl_single,
            url,
            config_dict
        )

    async def crawl_batch(self, urls: List[str], config_dict: dict) -> List[dict]:
        """异步执行批量爬取"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._run_crawl_batch,
            urls,
            config_dict
        )

    def cleanup(self):
        """清理资源"""
        self._executor.shutdown(wait=True)


# 全局执行器实例
_crawl4ai_executor = None


def get_crawl4ai_executor() -> Crawl4AIExecutor:
    """获取全局 Crawl4AI 执行器实例"""
    global _crawl4ai_executor
    if _crawl4ai_executor is None:
        _crawl4ai_executor = Crawl4AIExecutor()
    return _crawl4ai_executor


class Crawl4AITool(BaseTool):
    """
    基于Crawl4AI的高效网页爬取工具

    特点：
    - 极速爬取：基于Playwright的异步爬取
    - 智能提取：自动转换为清洁的Markdown格式
    - 批量处理：支持并发爬取多个URL
    - 内容过滤：智能过滤无用内容
    - 简单易用：一个工具解决所有网页爬取需求
    """

    name: str = "crawl4ai"
    description: str = """
基于Crawl4AI的高效网页爬取工具，专为AI和LLM优化。

核心功能：
- crawl_single: 爬取单个网页，获取清洁的Markdown内容
- crawl_batch: 批量并发爬取多个网页
- crawl_with_search: 先搜索再爬取最相关的网页

特点：
✅ 极速爬取 - 基于Playwright异步引擎
✅ 智能提取 - 自动过滤广告、导航等无用内容
✅ AI友好 - 输出清洁的Markdown格式
✅ 批量处理 - 支持并发爬取提升效率
✅ 内容质量 - 智能评估内容价值

适用场景：
🔍 获取实时信息（新闻、天气、股价）
📚 研究资料收集
🤖 为AI提供高质量训练数据
📊 竞品分析和市场调研
"""

    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["crawl_single", "crawl_batch", "crawl_with_search"],
                "description": "爬取操作类型"
            },
            "url": {
                "type": "string",
                "description": "要爬取的单个URL（用于crawl_single）"
            },
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要批量爬取的URL列表（用于crawl_batch）"
            },
            "search_query": {
                "type": "string",
                "description": "搜索查询词（用于crawl_with_search）"
            },
            "max_results": {
                "type": "integer",
                "default": 10,
                "description": "最大结果数量"
            },
            "include_images": {
                "type": "boolean",
                "default": False,
                "description": "是否包含图片信息"
            },
            "wait_for": {
                "type": "string",
                "description": "等待特定元素加载（CSS选择器）"
            },
            "extract_goal": {
                "type": "string",
                "description": "内容提取目标，帮助过滤相关内容"
            }
        },
        "required": ["action"],
        "dependencies": {
            "crawl_single": ["url"],
            "crawl_batch": ["urls"],
            "crawl_with_search": ["search_query"]
        }
    }

    async def execute(
        self,
        action: str,
        url: Optional[str] = None,
        urls: Optional[List[str]] = None,
        search_query: Optional[str] = None,
        max_results: int = 3,
        include_images: bool = False,
        wait_for: Optional[str] = None,
        extract_goal: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """执行Crawl4AI爬取操作"""

        try:
            if action == "crawl_single":
                return await self._crawl_single_url(url, include_images, wait_for, extract_goal)
            elif action == "crawl_batch":
                return await self._crawl_batch_urls(urls, include_images, wait_for, extract_goal)
            elif action == "crawl_with_search":
                return await self._crawl_with_search(search_query, max_results, include_images, extract_goal)
            else:
                return ToolResult(error=f"未知操作: {action}")

        except Exception as e:
            logger.error(f"Crawl4AI tool error: {e}")
            return ToolResult(error=f"爬取失败: {str(e)}")

    async def _crawl_single_url(
        self,
        url: str,
        include_images: bool,
        wait_for: Optional[str],
        extract_goal: Optional[str]
    ) -> ToolResult:
        """爬取单个URL"""

        logger.info(f"🕷️ Crawl4AI 爬取单个URL: {url}")

        try:
            # 准备配置字典
            config_dict = {
                'word_count_threshold': 10,
                'excluded_tags': ["script", "style", "nav", "footer", "aside"] if not include_images else ["script", "style"],
                'exclude_external_links': True,
                'remove_overlay_elements': True,
                'page_timeout': 30000,
                'wait_for': wait_for
            }

            # 使用执行器在独立线程中运行
            executor = get_crawl4ai_executor()
            result = await executor.crawl_single(url, config_dict)

            if result['success']:
                # 提取页面信息
                page_info = self._extract_page_info_from_dict(result, extract_goal)

                return ToolResult(
                    output=json.dumps(page_info, ensure_ascii=False, indent=2)
                )
            else:
                return ToolResult(error=f"爬取失败: {result['error_message']}")

        except ImportError:
            return ToolResult(error="Crawl4AI 未安装。请运行: pip install crawl4ai")
        except Exception as e:
            logger.error(f"Crawl4AI single crawl error: {e}")
            return ToolResult(error=f"爬取URL失败: {str(e)}")

    async def _crawl_batch_urls(
        self,
        urls: List[str],
        include_images: bool,
        wait_for: Optional[str],
        extract_goal: Optional[str]
    ) -> ToolResult:
        """批量爬取多个URL"""

        logger.info(f"🕷️ Crawl4AI 批量爬取 {len(urls)} 个URL")

        try:
            # 准备配置字典
            config_dict = {
                'word_count_threshold': 10,
                'excluded_tags': ["script", "style", "nav", "footer", "aside"] if not include_images else ["script", "style"],
                'exclude_external_links': True,
                'remove_overlay_elements': True,
                'page_timeout': 30000,
                'wait_for': wait_for
            }

            # 使用执行器在独立线程中运行
            executor = get_crawl4ai_executor()
            results = await executor.crawl_batch(urls, config_dict)

            batch_results = []
            successful_count = 0

            for result in results:
                if result['success']:
                    page_info = self._extract_page_info_from_dict(result, extract_goal)
                    batch_results.append(page_info)
                    successful_count += 1
                else:
                    batch_results.append({
                        "url": result['url'],
                        "status": "failed",
                        "error": result['error_message'],
                        "title": "",
                        "content": "",
                        "content_length": 0
                    })

            # 按内容质量排序
            batch_results.sort(key=lambda x: x.get("content_length", 0), reverse=True)

            summary = {
                "total_urls": len(urls),
                "successful_crawls": successful_count,
                "failed_crawls": len(urls) - successful_count,
                "success_rate": f"{(successful_count/len(urls)*100):.1f}%",
                "extract_goal": extract_goal,
                "results": batch_results,
                "summary": f"成功爬取 {successful_count}/{len(urls)} 个网页"
            }

            return ToolResult(
                output=json.dumps(summary, ensure_ascii=False, indent=2)
            )

        except ImportError:
            return ToolResult(error="Crawl4AI 未安装。请运行: pip install crawl4ai")
        except Exception as e:
            logger.error(f"Crawl4AI batch crawl error: {e}")
            return ToolResult(error=f"批量爬取失败: {str(e)}")

    async def _crawl_with_search(
        self,
        search_query: str,
        max_results: int,
        include_images: bool,
        extract_goal: Optional[str]
    ) -> ToolResult:
        """先搜索再爬取最相关的网页"""

        logger.info(f"🔍 Crawl4AI 搜索并爬取: {search_query}")

        try:
            # 1. 先执行搜索
            from app.tool.web_search import WebSearch
            web_search = WebSearch()

            search_result = await web_search.execute(
                query=search_query,
                num_results=max_results,
                fetch_content=False  # 不获取内容，只要URL
            )

            if search_result.error:
                return ToolResult(error=f"搜索失败: {search_result.error}")

            # 2. 提取搜索到的URL
            urls = [item.url for item in search_result.results]

            # 3. 使用Crawl4AI批量爬取
            crawl_result = await self._crawl_batch_urls(urls, include_images, None, extract_goal)

            if crawl_result.error:
                return crawl_result

            # 4. 整合搜索和爬取结果
            crawl_data = json.loads(crawl_result.output)

            integrated_result = {
                "search_query": search_query,
                "extract_goal": extract_goal,
                "search_results_count": len(urls),
                "crawl_summary": crawl_data,
                "top_results": crawl_data.get("results", [])[:max_results],
                "strategy": "搜索引擎 + Crawl4AI 高效爬取"
            }

            return ToolResult(
                output=json.dumps(integrated_result, ensure_ascii=False, indent=2)
            )

        except Exception as e:
            return ToolResult(error=f"搜索爬取失败: {str(e)}")

    def _extract_page_info_from_dict(self, result_dict: dict, extract_goal: Optional[str]) -> Dict[str, Any]:
        """从结果字典中提取页面信息"""

        # 提取标题
        title = ""
        metadata = result_dict.get('metadata', {})
        if metadata:
            title = metadata.get("title", "")

        if not title and result_dict.get('cleaned_html'):
            import re
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', result_dict['cleaned_html'], re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()

        markdown_content = result_dict.get('markdown', '')

        # 评估内容质量
        content_quality = self._assess_content_quality(markdown_content)

        # 提取关键信息（如果有提取目标）
        key_info = ""
        if extract_goal:
            key_info = self._extract_relevant_content(markdown_content, extract_goal)

        return {
            "url": result_dict.get('url', ''),
            "status": "success",
            "title": title,
            "content_length": len(markdown_content),
            "content_quality_score": content_quality,
            "content_preview": markdown_content[:800],  # 前800字符预览
            "full_content": markdown_content,
            "key_information": key_info,
            "extract_goal": extract_goal,
            "crawl_time": result_dict.get('response_time', 0)
        }

    def _extract_page_info(self, crawl_result, extract_goal: Optional[str]) -> Dict[str, Any]:
        """从爬取结果中提取页面信息（兼容性方法）"""

        # 提取标题
        title = ""
        if hasattr(crawl_result, 'metadata') and crawl_result.metadata:
            title = crawl_result.metadata.get("title", "")

        if not title and crawl_result.cleaned_html:
            import re
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', crawl_result.cleaned_html, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()

        # 评估内容质量
        content_quality = self._assess_content_quality(crawl_result.markdown)

        # 提取关键信息（如果有提取目标）
        key_info = ""
        if extract_goal:
            key_info = self._extract_relevant_content(crawl_result.markdown, extract_goal)

        return {
            "url": crawl_result.url,
            "status": "success",
            "title": title,
            "content_length": len(crawl_result.markdown),
            "content_quality_score": content_quality,
            "content_preview": crawl_result.markdown[:800],  # 前800字符预览
            "full_content": crawl_result.markdown,
            "key_information": key_info,
            "extract_goal": extract_goal,
            "crawl_time": getattr(crawl_result, 'response_time', 0)
        }

    def _assess_content_quality(self, content: str) -> float:
        """评估内容质量"""
        if not content:
            return 0.0

        # 简单的质量评估指标
        word_count = len(content.split())
        line_count = len(content.split('\n'))

        # 基于长度和结构的质量评分
        length_score = min(word_count / 500, 1.0)  # 500词为满分
        structure_score = min(line_count / 20, 1.0)  # 20行为满分

        return (length_score * 0.7 + structure_score * 0.3)

    def _extract_relevant_content(self, content: str, extract_goal: str) -> str:
        """根据提取目标提取相关内容"""
        if not extract_goal or not content:
            return ""

        # 简单的关键词匹配提取
        goal_keywords = extract_goal.lower().split()
        content_lines = content.split('\n')

        relevant_lines = []
        for line in content_lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in goal_keywords):
                relevant_lines.append(line.strip())

        return '\n'.join(relevant_lines[:10])  # 最多返回10行相关内容
