import pandas as pd
import time
import os
from app import create_app
from app.services.nl2vis import nl2vis


def run_evaluation():
    print("🚀 开始执行 NL2VIS 自动化基准测试 (Benchmark)...")

    # 1. 加载测试集
    test_file = os.path.join('data', 'test_cases.csv')
    if not os.path.exists(test_file):
        print(f"❌ 找不到测试集文件: {test_file}")
        return

    try:
        df_tests = pd.read_csv(test_file, encoding='utf-8')
    except UnicodeDecodeError:
        df_tests = pd.read_csv(test_file, encoding='gbk')
    results = []

    # 2. 初始化 Flask 应用上下文 (必须有，否则数据库查不了)
    app = create_app()
    with app.app_context():
        # 3. 循环执行测试
        total = len(df_tests)
        success_count = 0

        for index, row in df_tests.iterrows():
            q_id = row['id']
            # 如果 MySQL 没建索引，第36题的 LEFT JOIN 会卡死数据库，直接跳过
            if q_id == 36:
                print(f"\n[{q_id}/{total}] 测试中... (此题因数据库性能原因跳过以防卡死)")
                continue
            difficulty = row['difficulty']
            query = row['query']

            print(f"\n[{q_id}/{total}] 测试中 ({difficulty}): {query}")

            start_time = time.time()

            # 调用你写好的核心逻辑
            response = nl2vis(query)

            latency = round(time.time() - start_time, 2)
            is_success = response.get('success', False)

            if is_success:
                success_count += 1
                chart_type = response.get('chart_type', 'unknown')
                print(f"  ✅ 成功 | 耗时: {latency}s | 图表: {chart_type}")
                results.append({
                    'id': q_id,
                    'difficulty': difficulty,
                    'query': query,
                    'status': 'Success',
                    'latency_sec': latency,
                    'chart_generated': chart_type,
                    'error_msg': ''
                })
            else:
                error_msg = response.get('error', 'Unknown Error')
                print(f"  ❌ 失败 | 耗时: {latency}s | 报错: {error_msg}")
                results.append({
                    'id': q_id,
                    'difficulty': difficulty,
                    'query': query,
                    'status': 'Failed',
                    'latency_sec': latency,
                    'chart_generated': '',
                    'error_msg': error_msg
                })

            # 为了防止触发 DeepSeek API 频率限制，稍微睡一下
            time.sleep(3)

    # 4. 保存结果并输出统计报告
    df_results = pd.DataFrame(results)
    output_file = os.path.join('data', 'evaluation_results.csv')
    df_results.to_csv(output_file, index=False, encoding='utf-8-sig')

    print("\n" + "=" * 40)
    print("📊 测试报告汇总 (Benchmark Report)")
    print("=" * 40)
    print(f"总测试用例: {total} 个")
    print(f"整体成功率: {(success_count / total) * 100:.1f}% ({success_count}/{total})")
    print(f"平均响应耗时: {df_results['latency_sec'].mean():.2f} 秒")

    # 按难度分组统计、、、、
    print("\n各难度成功率:")
    for diff in ['Easy', 'Medium', 'Hard']:
        subset = df_results[df_results['difficulty'] == diff]
        if not subset.empty:
            diff_success = len(subset[subset['status'] == 'Success'])
            print(f" - {diff}: {(diff_success / len(subset)) * 100:.1f}% ({diff_success}/{len(subset)})")

    print(f"\n✅ 详细测试结果已保存至: {output_file}")


if __name__ == '__main__':
    run_evaluation()