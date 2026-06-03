# Go 纵深 #10：反射与代码生成

## reflect 包
```go
t := reflect.TypeOf(obj)   // 获取类型信息
v := reflect.ValueOf(obj)  // 获取值信息
k := t.Kind()              // 基础类型（struct/slice/map 等）

// 遍历 struct 字段
for i := 0; i < t.NumField(); i++ {
    f := t.Field(i)
    val := v.Field(i)
    fmt.Printf("%s: %v (tag: %s)\n", f.Name, val.Interface(), f.Tag.Get("json"))
}

// 调用方法
method := v.MethodByName("MethodName")
result := method.Call([]reflect.Value{reflect.ValueOf(arg)})
```

## struct tag 解析
```go
type User struct {
    Name  string `json:"name" db:"user_name" validate:"required"`
    Email string `json:"email" validate:"email"`
}
// reflect.StructField.Tag.Get("json") → "name"
```

## 模拟 JSON 序列化（不带编码器）
```go
func toMap(v any) map[string]any {
    result := make(map[string]any)
    t := reflect.TypeOf(v)
    val := reflect.ValueOf(v)
    for i := 0; i < t.NumField(); i++ {
        field := t.Field(i)
        jsonTag := field.Tag.Get("json")
        name := strings.Split(jsonTag, ",")[0]
        if name == "" { name = field.Name }
        result[name] = val.Field(i).Interface()
    }
    return result
}
```

## 代码生成工具
- `stringer`：为常量类型自动生成 String() 方法
  - `//go:generate stringer -type=Pill`
- `genny`：泛型代码生成（Go 1.18 前）
- `counterfeiter`：从接口生成 mock
- `oapi-codegen`：从 OpenAPI spec 生成客户端/服务端代码

## 性能注意
反射比直接调用慢 10-100 倍，不适合热路径
