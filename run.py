from app import create_app

# 创建 app 实例
app = create_app()

if __name__ == '__main__':
    # debug=True 开发时自动重载，报错时显示详细信息
    app.run(debug=True, host='0.0.0.0', port=5000)