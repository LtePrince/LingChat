本文写作时目的是为了帮助钦灵快速理解golang代码，此后也可作为帮助其他golang新人快速上手的新手指南。

### 1. 环境搭建及运行

上手一个新项目第一件事当然是先跑起来再说，翻代码都是后面的事。

首先你需要一个golang，你可以从[golang官网](https://go.dev/)下载安装包，也可以在各自系统使用包管理器或者编程环境管理器各显神通，这里不再赘述。

关于golang的基本教程，已经有大量相当高质量的教程可供参考，这里就不再重复造轮子，不过对于初步入门我可以推荐[golang官方互动式教程](https://go.dev/tour/welcome/1)，可以对语法和语言特性有一些初步的了解。

拉下代码进入golang项目的根目录，现在是`LingChat/backend/go-impl`, 正确填写配置（现在是.env）并运行以下几条命令：
```bash
go mod tidy
go generate ./...
go mod tidy
go run ./...
```

一些解释：
- `go mod tidy`可以大致理解为超级智能版的 `pip freeze > requirements.txt`+`pip install requirements.txt`，实际上它不仅会根据代码分析出必要依赖、下载和更新依赖，还会清理无用依赖，由于实在过于轮椅它事实上在go开发流程中地位类似早些年Windows的刷新键一样，虽然理论上来说只要开发时维护依赖的习惯良好，这里运行项目之前的必要准备中其实这两个go mod tidy是都可以去掉的，但反正没事按两下刷新总没坏处...
- `go generate`是当项目中引入了一些需要代码生成（后面会解释）的库时执行它们所需要的生成步骤的统一入口。虽然单独执行它们自身也可以，不过`go generate`会代你执行所有需要的。 `./...`是golang命令行工具特有的语法，意思是当前目录及所有子目录下的文件，在这里也就是会找到并执行整个项目中所有使用了`go generate`的位置。
- `go run`是编译运行的快捷方式，如果你想要只编译可以`go build`，然后手动执行编译好的二进制文件。顺带一提这里`./...`倒其实不是意味着需要把所有文件囊括一遍才能运行那么麻烦，它其实是找到了位于`./cmd/app`下的`package main`，并从这里开始构建的。也就是说，`go run ./cmd/app`效果是一样的

> 如果前面没出问题，此时应该能看到程序正常启动并且打印出banner了。恭喜！你已经堂堂上手了（

### 2. 项目结构

跑起来之后就该来看看项目结构了。这里我采用了稍微有一些go风格但大体上比较中性的项目结构设计，也就是说很大程度上也对其他语言（主要指如果你未来想进一步重构以规整python代码的结构）有不少借鉴意义。

#### 先看第一层：

- `cmd`目录存放程序入口，也就是`main`包所在的代码。如你所见因为现在项目还比较小型，所以`cmd`下只有`app`一个子目录，也就是程序本身的入口。对于比较大的项目，`cmd`下可能还会有一些辅助工具或脚本的入口，甚至可能大型项目的程序本身是多进程共用很多项目内代码但各自执行不同任务的，那么这些情况它们会在`cmd`下各自占据一个子目录。顺带一提，这种情况下上面所说的`go run ./...`会因为找到多个入口而报错，这种时候必须明确指定想运行的`main`包位置。
- `internal`是golang的关键字，这个目录下的所有代码默认是不导出的，无论代码中的内容如何表示。它用来存放程序的内部逻辑，避免被第三方意外调用。它的内部结构是最多的，后面单独讲。
- `api`层是整个系统业务数据（在这里就是聊天，等等）的出入口，是负责接受前端传来的请求的第一步，返回响应的最后一步。
  - 它主要负责接受并分发用户的各类请求，检验和转换用户输入（例如格式和类型，还包括防范注入攻击），验证用户身份等（因为用户身份往往在cookies或者请求的Header中，属于一种元信息）。处理好的数据会发送给下文会提到的`service`层做进一步的处理，并将其处理结果格式化为预定的返回格式交还给客户端。
  - 此外，`api`层还存放api定义和请求/响应结构的定义。这也是为什么这部分在`internal`外面，这使得其它项目希望向当前项目的实例发送请求时可以直接引用相关定义，包括有些项目会将Client代码直接也放在`api`层作为sdk一并提供，那么其他人只需要引入api层即可直接调用相关方法。
- `pkg`层主要存放一些可以复用但本身和项目没有太强绑定性的工具类代码， 比如一些特定的算法，一般是即用即走的类型最好，不适合把一些需要初始化一整个实例并围绕这个实例工作的package放进去。

#### 再看`internal`内：

- `config`字面意思。
- `clients`各种客户端。你要发送请求到别的服务，例如DeepSeek的API，此时对面的角色就是服务端，而你是客户端（尽管相对于LingChat的使用者来说你是服务端)。一般我们会用单独的实例负责向某个特定的服务发送请求，或是使用对方提供好的sdk，这样的结构就是调用每个服务的客户端。
- `service`这个和接下来的`data`是重点部分。
  - `service`层是业务逻辑处理的核心部分。简单来说，对于一个特定的功能（例如聊天），先做什么后做什么（请求llm，情绪预测，语音生成)，核心的工作流程编排都在这里完成。
  - 当涉及到数据存储和查询时，往往会在这里调用即将提到的`data`层方法。
- `data`层,有时也叫`repository`层，负责对数据存储和访问等操作的抽象和封装，当然这里数据存储的一个大头就是指的数据库。
  - 抽象的意义在于抹平具体的数据处理实现细节。无论你使用Mysql还是sqlite，是否使用ORM，都可以给`service`层提供相同的方法

> 回顾一下可以发现，这个项目结构的数据流向有一个明确的主干，也就是API-Service-Data。恭喜你发现了后端最经典也最基础的「三层架构」设计（
> 
> 有一个挺巧妙的比喻，后端是一家餐厅，API层就是服务员给顾客上菜，Service层就是后厨，Data层就是管理和采买食材的后勤
> 
> 对于这个项目而言，Client会显得比Data层内容更多一些。这也有一定道理，把三层架构视为纵向，Data和Client确实处于同一深度。
> 
> 这个架构不仅几乎是后续微服务、领域驱动设计等相当多复杂的系统设计的出发点，其本身也相当能打，既不会对特别小型的项目显得过重，也可以承载相当复杂程度的业务逻辑和代码量而没有非常明确急切的必要切换到后续更复杂的架构设计。
> 
> 此外它对于绝大多数适合编写web后端的语言都是比较优秀的工程实践，直接套用都不会有太大问题，拥有很高的实用性和借鉴意义（


