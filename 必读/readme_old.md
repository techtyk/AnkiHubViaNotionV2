一、开发目标：
这个项目是一个anki插件，插件的名字是“AnkiHubViaNotion”，此项目文件夹已经放在了addon21文件夹下。插件要实现的功能是：
1.1-将notion作为anki卡片的托管平台，能够实现anki和notion之间卡片的双向同步。
1.2-为anki添加一个设置界面，能够供用户配置有关选项。

二、技术路径的选择：
2.1-禁止依赖ankiconnect插件来访问anki数据库（因为http协议访问anki卡片开销较大），要求直接使用anki内部的方法实现高效访问anki数据库。
2.2-使用notion官方提供的notionclient库，来访问notion数据库。

三、重点：
3.1项目作为anki插件来运行，而不是在conda虚拟环境中，因此第三方包/库都应该放在项目的lib文件夹下
3.2可能需要建立meta.json、config.json、config.md等文件，以便anki对插件的正确识别
3.3功能的实现不要全部挤在一个python脚本里，应该符合面向对象开发的基本原则，便于调试和发现错误。比如：每个python脚本只包含一个类，每个类只负责自己的事情，尽量减少和其他类的交互。
3.4anki目前的版本是24.11版本，anki插件开发有关资料需要查阅https://addon-docs.ankiweb.net/和https://forums.ankiweb.net/
3.5无论是anki卡片还是从anki导入notion中的卡片，这些卡片的字段都包括两种类型，一种是模板字段，一种是元数据字段，模板字段是指Note Type具有的字段，元数据字段指的是卡片id、学习数据、牌组名等字段。元数据字段对于从notion导回anki，重建学习信息非常重要，因此需要将这些元数据字段一并从anki导入notion中。

四、要实现的功能：
4.1-有关配置选项能够在插件的设置界面中供用户配置：
设置界面的字段包括：
4.1.1 notion_token
    notion的token（notion中私有集成的token）
4.1.2 notion_database_url
    要同步的notion数据库（已经关联到了notion_token）的url（自动从中提取id）
4.1.3 anki_query_string
    anki中要同步的卡片对应的查询字符串（anki中，在卡片浏览器中输出查询字符串就能查询对应的卡片）
4.1.4 duplicate_handling_way
    这个字段的值可由用户修改，它决定了导入时插件处理重复卡片方式，字段的值包括三种
    -keep：从A平台导入B平台的时候（无论是从notion导入anki还是从anki导入notion），如果遇到重复卡片，保留B平台重复的卡片
    -overwrite：从A平台导入B平台的时候，如果遇到重复卡片，覆盖B平台重复的卡片
    -copy：从A平台导入B平台的时候，如果遇到重复卡片，正常导入重复卡片，即使这会导致重复


4.2-为插件添加若干下拉选项（在anki的工具菜单中），能够供用户选择同步的方向（anki2notion还是notion2anki）。
这些选项包括：
4.2.1 anki2notion
    当用户点击这个选项的时候，根据anki_query_string将anki中的卡片导入notion，注意需要将anki中的卡片id、学习数据、牌组名等元数据一并导入notion，以便未来将notion中的卡片导回到anki中的时候，能够恢复这些数据。
    注意：将anki卡片导入notion的时候，是以anki中的待导入卡片的字段为基准进行导入操作，如果notion中不存在anki中待导入卡片的字段，就创建这些字段。
4.2.2 notion2anki
    当用户点击这个选项的时候，将notion中用户当前在notion的web页面中选中的卡片（notion网页中卡片左侧会显示被勾选）导回到anki中原来的牌组（需要用户为希望导回anki的卡片添加标签：“readyMove”，筛选出具有这个标签的卡片，然后进行导入anki的工作）
    注意：从notion中导入anki笔记的时候：
    1-导入notion中全部的元数据字段；
    2-对于模板字段，只导入待导入笔记的非空字段。
    3-在1、2的前提条件下，如果不存在某个需要导入的字段，才为模板新建这个字段


五、插件应尽可能用户友好
5.1 将anki卡片导入notion之前自动检测notion字段，当notion数据库不存在anki卡片对应的字段的时候，插件应能够自动创建这些字段；
5.2 将anki卡片导入notion之前自动检测notion数据库中是否存在重复的卡片，如果存在重复的卡片，根据用户的选项自动处理这些卡片；
5.3 将notion卡片导入anki之前自动检测是否被用户选中/具有readymove标签（具体是哪种情况取决于是否能够获取用户对卡片的选择情况，如果能获取，就检测卡片是否被用户选中就行），如果被选中，则将卡片按其元数据（deckname、tags、creation_time、modification_time、review_count、ease_factor、interval、card_type、due_date、suspended、lapses）导入anki中；
5.4 将notion中的卡片导入anki之前自动检测anki数据库中是否存在重复的卡片，如果存在重复的卡片，根据用户的选项自动处理这些卡片；
5.5 在5.3中已经提到将notion卡片导入anki是按照元数据导入，如果anki中不存在这些元数据，则自动创建这些字段，比如不存在某个卡片对应的牌组，则自动创建这个卡片对应的牌组，不存在某个卡片对应的tags，则自动创建这些tags，不存在某个卡片对应的模板，则自动创建这个卡片对应的模板，等等；
5.6 如果卡片存在多媒体文件，应该将多媒体文件导入notion的正文部分(应该是children字段)中（notion不支持导入本地存储的多媒体文件，本插件只需将多媒体文件的url导入notion的正文即可）
5.7 重复笔记的检验逻辑:无论是从notion导入anki还是从anki导入notion，重复笔记都应该是根据模板名称以及首字段名称是否相同来确定。（模板名称相同且首字段相同，则为重复笔记）
    应该确保：
    1）将anki导入notion时，导入了笔记的首字段信息；比如，如果某个笔记的首字段是“正面”，新建一个字段叫做First Field，First Field的内容为首字段的名称“正面”
    2）将notion导入anki时，根据notion中笔记的模板名称Note Type和笔记首字段内容来判定，只有当NoteType和首字段内容都相同的时候，才判定为是重复笔记；比如 First Field的内容是正面，那除了比较模板名称Note Type，还需要比较“正面”这个字段的值是否相同，据此确定是不是重复笔记。
    3）将anki导入notion的时候，也是一样的方法，判定模板名称是否相同，判定首字段是否相同，都相同，则为重复笔记。
5.8 用户应该要能够选择是否保留源侧的笔记（不保留，则删除源侧笔记）
5.9 多语言支持，用户可以选择插件应该显示的语言
5.10 为提高用户在notion中编辑修改并将笔记导入 anki的自由度，需要添加一功能，该功能为将notion中的正文内容转换为anki中的新字段的值，并更新 anki 模板。
	为了实现该功能，下拉菜单中需要增加一个新的选项：“将 notion 笔记导入anki 时，是否保留 notion 正文”
		1）如果用户勾选该选项，则笔记从 notion导入anki的时候，会检查 notion 正文是否非空，如果是空字段，则不进行处理，如果非空，则将notion中的正文内容转换为anki中的新字段，名为“notion正文”，并保留notion中的正文内容作为“notion正文”字段的值。
		此外，新字段将自动被添加到笔记背面，在背面的默认内容的底部显示：“<div class="notionart">{{notion正文}}</div>”。样式为：“.notionart {color: gray; font-style: italic;}”
		2）如果用户不勾选该选项，则笔记从 notion导入anki的时候，无视notion中笔记的正文内容，不进行模板的修改和内容的导入。
		3）尽可能减少算法的复杂度，减少不必要的计算。
		4）notion 中的正文支持 markdown等格式，需要考虑 这些 格式对 anki 模板的影响。（尽可能保证 notion 正文中原有格式能够在 anki中显示）
	该功能的实现过程包括4个步骤：
	1-下拉菜单增加新的选项：“将 notion 笔记导入anki 时，是否保留 notion 正文”，并设置当该选项被点击时，触发notion2anki 中对应的函数“save_notion_children_and_update_anki_model”
	 在 notion2anki 中添加新的函数save_notion_children_and_update_anki_model函数，该函数由三个子函数组成：
	 1）extract_notion_children
	 	该函数的作用是“提取并返回 notion 中的正文字段”
		返回值：notion 正文字段的原始值（名为 notion_children）
	 2）process_notion_children
	 	该函数的作用是“判断 notion 中的正文字段是否非空，如果为空，直接返回返回notion 中的正文字段；如果非空，对提取到的notion 正文进行格式处理，以便notion 中的各种格式能够在 anki中正常显示”
		返回值：notion 正文字段处理后的结果(名为 processed_notion_children）)
	 3）update_anki_model_via_notion_children
	 	该函数的作用是"接受 process_notion_children返回的“processed_notion_children”，判断其是否非空，如果为空，直接返回；否则，使用processed_notion_children更新该笔记的原始模板，这包括：添加新的字段 notion正文、添加新的样式 notionart、在笔记对应卡片的背面内容模板的底部添加<div class="notionart">{{notion正文}}</div>
		返回值：无
	 在第一步中，无需实现这三个函数，只需要编写好大概的结构或框架即可。
	2-查阅资料，调研并实现 extract_notion_children函数；
	3-查阅资料，调研并实现process_notion_children函数；
	4-实现update_anki_model_via_notion_children；
	5-(重要)
	5.1-修改“update_existing_note”函数和“create_new_note”函数，在该函数运行结束前增加判断"if config.get('retain_notion_children'):",如果该判断为真且processed_notion_children非空，则调用write_notion_children_to_anki_note函数，将processed_notion_children作为笔记中的“notion正文”字段的值；否则，不进行任何操作。
	5.2-实现write_notion_children_to_anki_note,该函数的作用是使用processed_notion_children作为笔记中的“notion正文”字段的值。
	在每个步骤实现完之后，你都需要在合适的位置添加print_all_var函数，以观察工作区的所有变量，方便进行调试分析。	
    6-修改anki2notion文件，以适应5：
    6.1-注意！如果笔记存在"notion正文"字段，无论是否是空字段，都应该注意，不应将该字段作为模板字段导入notion中。
    6.2-在将anki笔记导入notion的时候，需要检查笔记是否存在非空的"notion正文"字段，如果存在，则将"notion正文"字段的内容作为notion笔记的正文内容。
