from pathlib import Path

from application.writing_spec import WritingSpecValidator, load_writing_spec


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "writing_specs/open_source_past.yaml"
HF_SPEC_PATH = REPO_ROOT / "writing_specs/open_source_past_huggingface.yaml"


def test_open_source_past_spec_accepts_aligned_draft():
    spec = load_writing_spec(SPEC_PATH)
    assert len(spec.judges) == 1
    assert spec.judges[0].id == "open-source-past-llm-judge"
    assert len(spec.reader) == 2
    assert any(rule.id == "reader-ai-war-jargon-density-limit" for rule in spec.reader_metrics)

    text = """
# 外篇：被俘获的胜利

开源赢了，但胜利并不等于归乡。源代码从黑盒里被释放，软件、计算机和互联网的知识进入公共空间；Stallman、GNU、Linux 与 Apache 点燃的火种，后来穿过 GitHub 和 Hugging Face 这样的广场。问题在于，广场一旦成为唯一入口，就开始拥有城墙的功能。

这不是因为开放失败，而是因为权力学会了不反对开放。IBM、MIT、PDP-10、Usenet 和 GPL 所代表的早期历史，说明封闭曾经依靠合同、律师、授权和金库；到了云厂商时代，封闭不再总是藏起代码，而是控制托管服务、分发入口、账号体系、默认选项和排名。

于是，公司和商业平台可以同时赞美开源、吸收开源、重新包装开源。服务器、数据库、容器、控制台、账单、API、搜索排序、企业采购、用户关系和网络效应，构成新的制度现场。一旦这些现场被云和平台接管，开放代码仍然开放，使用道路却可能封闭。

这就是被俘获的胜利。帝国不必宣布开源违法，也不必重新把共享知识锁回黑盒；它只要让离开变得昂贵，让重建变得困难，让每一次部署都经过同一个控制台和同一套账号。权力回来了，不是以禁令的形式，而是以方便的形式。

这样的变化必须落在制度细节里看。早期软件行业把授权写进合同，把源代码放在只有雇员能够进入的实验室和机房里；后来的平台时代，则把协作、身份、发布、支付、企业采购和搜索排序做成一整套服务。用户得到的不是单一程序，而是一条被精心铺好的路径。

路径越顺滑，选择越难被察觉。开发者当然还能下载源码，也当然还能自建服务器；可是数据库迁移、容器镜像、API 兼容、团队权限、审计日志和账单系统会一层层抬高离开的成本。这里的关键不是某家公司善恶如何，而是便利如何成为新的治理技术。

所以这段历史仍然未完成。自由不是许可证上的一句话，也不是仓库里的星数，而是活人能否继续选择、复制、离开和重建。每一个人仍然要保存火种，因为归乡不是一次抵达，而是一代又一代人继续拆墙的劳动。
"""
    report = WritingSpecValidator(spec).validate(text)

    assert report.passed is True


def test_open_source_past_spec_rejects_fictional_ai_tool_drift():
    spec = load_writing_spec(SPEC_PATH)
    text = """
# 外篇：新黑盒之后

凌晨两点，一个维护者坐在出租屋里，看着 Merge 按钮。
年轻贡献者说：它自己修好了，测试全绿。
AI 编程助手生成了 commit message，云端 IDE 让一切都更快。
本文认为 API 调用和自动补全正在改变开发效率，由此可见我们需要关注新工具。
"""
    report = WritingSpecValidator(spec).validate(text)

    assert report.passed is False
    assert any(finding.rule_id == "fictional-maintainer-scene" for finding in report.findings)
    assert any(finding.rule_id == "ai-tool-column-drift" for finding in report.findings)


def test_open_source_past_spec_rejects_default_entrance_negative_example():
    spec = load_writing_spec(SPEC_PATH)
    text = (
        REPO_ROOT / "writing_specs/examples/open_source_past/negative_default_entrance_generated.md"
    ).read_text(encoding="utf-8")
    report = WritingSpecValidator(spec).validate(text)

    assert report.passed is False
    assert any(finding.rule_id == "negative-default-entrance-generated" for finding in report.findings)
    assert any(finding.rule_id == "paragraph-breath-not-fragmented" for finding in report.findings)
    assert any(finding.rule_id == "motif-density-limit" for finding in report.findings)


def test_open_source_past_spec_rejects_ai_war_jargon_wall_for_lay_reader():
    spec = load_writing_spec(SPEC_PATH)
    text = """
# 外篇：伪善者的城墙

Stallman、GNU、Linux、Apache、GitHub 和 Hugging Face 之后，开源、源代码、软件、计算机和互联网的历史仍然围绕黑盒、流亡、归乡、火种和共享知识展开。因为权力、公司、商业、平台、云、封闭、开放、俘获和金库会不断回来，所以活人仍然必须继续选择。

IBM、MIT、PDP-10、Usenet、GPL、许可证、基金会、云厂商、托管服务、分发入口、账号体系、默认选项和排名说明了历史事件如何变成制度机制。实验室、合同、律师、授权、服务器、数据库、容器、控制台、账单、API、搜索排序、企业采购、用户关系和网络效应，则说明技术事实不是孤立名词，而是被权力重新组织的道路。

Anthropic、OpenAI、Claude、Palantir、AWS、classified networks、mission workflows、intelligence analysis、modeling and simulation、operational planning、cyber operations、system card、alignment、national security、responsible deployment、public sector、AI、模型、训练数据、评测体系、部署通道、反馈回路、政府合同、国防、情报、军方、网络行动、军事模拟、战前预警、战争机器、平民和风险被连续堆在一起，读者只能看见名词墙，却看不见一个人如何进入这件事。
"""
    report = WritingSpecValidator(spec).validate(text)

    assert report.passed is False
    assert any(finding.rule_id == "reader-ai-war-jargon-density-limit" for finding in report.findings)


def test_open_source_past_huggingface_spec_accepts_historical_narrative_draft():
    spec = load_writing_spec(HF_SPEC_PATH)
    assert spec.id == "open-source-past-huggingface"
    assert len(spec.judges) == 1
    assert spec.judges[0].id == "open-source-past-huggingface-llm-judge"

    text = """
# 第七章：模型广场

Hugging Face 的故事，不能从平台开始讲。它最初更像一个误入歧路又及时转身的项目。2016 年，Clément Delangue 和他的同伴们试图做一个聊天机器人入口；后来，Thomas Wolf 和自然语言处理社区让另一个东西浮出水面：真正缺少的不是一个会说话的应用，而是一条让模型可以被共享、下载、解释和复现的道路。

这条道路后来有了名字：Transformers。它不是一座宏伟宫殿，而是一组普通开发者能安装的工具。研究者把论文里的模型挪到代码里，学生第一次可以在自己的机器上调用 tokenizer 和 pipeline，工程师不必从零解释每一层架构。也就是说，模型开始像过去的源代码一样，获得了一种可以被别人接手的形状。

随后出现的是 Hub。Hub 把权重、数据集、推理示例和仓库放在同一个公共空间里。model card 和 dataset card 看起来只是说明文档，实际却改变了模型发布的伦理：你不能只把文件扔到广场上，你还要说明它从哪里来、适合什么任务、有哪些限制、别人怎样复现。开源在这里不再只是代码公开，而是把一整条知识链留下痕迹。

这正接住了《开源往事》里更早的火种。Stallman 要求人们能读源代码，Linux 和 GitHub 让协作成为日常；到了 Hugging Face，问题变成了人们能否读取权重、追问训练数据、理解许可证、复制评测，并在算力允许的地方重新运行模型。模型不是传统软件。源代码可以被阅读，权重却需要下载、显存、推理服务和微调脚本才能重新活过来。

所以，Hugging Face 在 AI 时代成了一个新的公共广场。Stable Diffusion 的扩散，LLaMA 泄露和后来的开放，Mistral、Qwen、DeepSeek 等开源权重模型的传播，都让这个广场变得拥挤。开发者在那里寻找起点，企业在那里寻找可用资产，研究者在那里留下公开承诺。它像 GitHub，但又不只是 GitHub，因为这里流通的不只是代码，还有算力账单和模型边界。

问题在于，公共广场一旦由一家公司托管，就会慢慢长出城门。平台提供托管、推荐、API、企业权限和推理服务，也就拥有了分配可见性的能力。谁出现在首页，谁被搜索排序看见，谁的仓库被标记为安全，谁的下载速度更稳定，这些决定不一定是恶意的，却会改变开源生态的重心。

这不是因为 Hugging Face 背叛了开源，而是因为平台本身有它的物理规律。服务器要钱，带宽要钱，合规要人，企业客户要求稳定，监管要求解释。于是开放的模型被放进更顺滑的道路里；道路越顺滑，默认入口就越有权力。结果是，开源权重仍然可以下载，但人们越来越依赖同一个广场来发现、比较和部署它们。

黑盒没有照旧回来。它换了一种形态。旧黑盒锁住源代码，新黑盒不一定锁住文件，它可能锁住可见性、推理入口、账号体系和企业服务。你仍然能看见火种，但火种被摆在平台搭好的橱窗里。换句话说，模型时代的自由不只是能否下载权重，还包括能否离开默认入口，能否复现训练与评测，能否在平台规则变化后继续重建。

这就是 Hugging Face 必须写进开源史的原因。它不是救世主，也不是反派。它是一个时代的剖面：开源获得了前所未有的传播速度，也第一次如此清楚地依赖平台来组织传播。公共广场越明亮，城墙的影子就越清晰。

结尾仍然回到那个旧问题。共享知识属于谁？属于上传者，属于平台，属于企业客户，还是属于每一个仍然愿意复制、解释、审计和重建它的人？答案仍然未完成。火种还在，但它不再只需要被点燃，它还需要被备份、迁移、复现，并在下一次门关上之前，留下另一条路。
"""
    report = WritingSpecValidator(spec).validate(text)

    assert report.passed is True, report.to_dict()


def test_open_source_past_huggingface_spec_rejects_plain_explainer_draft():
    spec = load_writing_spec(HF_SPEC_PATH)
    text = (
        REPO_ROOT / "writing_specs/examples/open_source_past_huggingface/negative_plain_explainer.md"
    ).read_text(encoding="utf-8")
    report = WritingSpecValidator(spec).validate(text)

    assert report.passed is False
    assert any(finding.rule_id == "huggingface-plain-explainer-register" for finding in report.findings)
    assert any(finding.rule_id == "fictional-platform-case" for finding in report.findings)
    assert any(finding.rule_id == "negative-huggingface-plain-explainer" for finding in report.findings)
