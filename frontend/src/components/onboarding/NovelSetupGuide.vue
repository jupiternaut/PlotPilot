<template>
  <n-modal
    v-model:show="modalOpen"
    :mask-closable="false"
    :close-on-esc="false"
    :closable="true"
    preset="card"
    title="新书设置向导"
    style="width: 94%; max-width: 960px; max-height: 92vh"
    :segmented="{ content: true, footer: true }"
  >
    <n-steps :current="currentStep" :status="stepStatus" size="small" class="wizard-steps">
      <n-step title="世界观" description="5维度框架" class="wizard-step-clickable" @click="goToStep(1)" />
      <n-step title="人物" description="主要角色" class="wizard-step-clickable" @click="goToStep(2)" />
      <n-step title="地图" description="地图系统" class="wizard-step-clickable" @click="goToStep(3)" />
      <n-step title="故事线" description="主线支线" class="wizard-step-clickable" @click="goToStep(4)" />
      <n-step title="开始" description="进入工作台" />
    </n-steps>

    <div class="step-content">
      <!-- 续传提示 -->
      <n-alert v-if="resumedFromStep > 1" type="success" style="margin-bottom: 16px">
        检测到之前的进度，已回到第 {{ resumedFromStep }} 步。您可以继续完成剩余设置。
      </n-alert>

      <!-- Step 1: Generate Worldbuilding + Style (SSE) -->
      <div v-if="currentStep === 1" key="step1" class="step-panel">
        <n-alert v-if="bibleError" type="error" :title="bibleError" style="margin-bottom: 16px; width: 100%">
          <div class="wizard-error-text">{{ bibleError }}</div>
        </n-alert>

        <!-- 生成中：骨架屏 + 流式数据 -->
        <div v-if="generatingBible" class="step-generating">
          <div class="generating-header">
            <div class="generating-icon">
              <n-icon size="36" color="#2080f0">
                <IconBook />
              </n-icon>
            </div>
            <div class="generating-text">
              <h3>{{ phaseMessage || '正在生成世界观...' }}</h3>
              <p class="generating-sub">AI 正在逐维度构建您的世界，出一个渲染一个</p>
            </div>
          </div>

          <WizardSkeleton
            type="worldbuilding"
            :active-dimension="activeDimension"
            :completed-dimensions="completedDimensions"
          >
            <template #core_rules>
              <div class="dimension-fields" v-if="worldbuildingData.core_rules && Object.keys(worldbuildingData.core_rules).length">
                <div v-for="(val, key) in worldbuildingData.core_rules" :key="key"
                  class="field-card" :class="{ 'field-card--streaming': activeDimension === 'core_rules' && activeField === key }">
                  <div class="field-card__title">{{ dimKeyLabels[key] || key }}</div>
                  <div class="field-card__content">{{ val }}<span v-if="activeDimension === 'core_rules' && activeField === key" class="streaming-cursor">▎</span></div>
                </div>
              </div>
            </template>
            <template #geography>
              <div class="dimension-fields" v-if="worldbuildingData.geography && Object.keys(worldbuildingData.geography).length">
                <div v-for="(val, key) in worldbuildingData.geography" :key="key"
                  class="field-card" :class="{ 'field-card--streaming': activeDimension === 'geography' && activeField === key }">
                  <div class="field-card__title">{{ dimKeyLabels[key] || key }}</div>
                  <div class="field-card__content">{{ val }}<span v-if="activeDimension === 'geography' && activeField === key" class="streaming-cursor">▎</span></div>
                </div>
              </div>
            </template>
            <template #society>
              <div class="dimension-fields" v-if="worldbuildingData.society && Object.keys(worldbuildingData.society).length">
                <div v-for="(val, key) in worldbuildingData.society" :key="key"
                  class="field-card" :class="{ 'field-card--streaming': activeDimension === 'society' && activeField === key }">
                  <div class="field-card__title">{{ dimKeyLabels[key] || key }}</div>
                  <div class="field-card__content">{{ val }}<span v-if="activeDimension === 'society' && activeField === key" class="streaming-cursor">▎</span></div>
                </div>
              </div>
            </template>
            <template #culture>
              <div class="dimension-fields" v-if="worldbuildingData.culture && Object.keys(worldbuildingData.culture).length">
                <div v-for="(val, key) in worldbuildingData.culture" :key="key"
                  class="field-card" :class="{ 'field-card--streaming': activeDimension === 'culture' && activeField === key }">
                  <div class="field-card__title">{{ dimKeyLabels[key] || key }}</div>
                  <div class="field-card__content">{{ val }}<span v-if="activeDimension === 'culture' && activeField === key" class="streaming-cursor">▎</span></div>
                </div>
              </div>
            </template>
            <template #daily_life>
              <div class="dimension-fields" v-if="worldbuildingData.daily_life && Object.keys(worldbuildingData.daily_life).length">
                <div v-for="(val, key) in worldbuildingData.daily_life" :key="key"
                  class="field-card" :class="{ 'field-card--streaming': activeDimension === 'daily_life' && activeField === key }">
                  <div class="field-card__title">{{ dimKeyLabels[key] || key }}</div>
                  <div class="field-card__content">{{ val }}<span v-if="activeDimension === 'daily_life' && activeField === key" class="streaming-cursor">▎</span></div>
                </div>
              </div>
            </template>
          </WizardSkeleton>

          <!-- 文风公约实时预览（SSE 生成中即可见） -->
          <div v-if="styleText" class="style-preview-generating">
            <div class="style-preview-header">
              <n-icon size="16" color="#18a058"><IconCheck /></n-icon>
              <span class="style-preview-title">文风公约</span>
              <n-tag size="tiny" type="success">已生成</n-tag>
            </div>
            <div class="style-preview-content">{{ styleText }}</div>
          </div>
        </div>

        <!-- 生成完成后显示可编辑预览 -->
        <div v-else-if="bibleGenerated" class="bible-preview">
          <n-alert type="success" title="世界观生成完成" style="margin-bottom: 16px">
            请查看并修改世界观设定和文风公约，确认后下一步将基于此生成人物和地点。
          </n-alert>

          <n-collapse :default-expanded-names="['worldbuilding', 'style']">
            <n-collapse-item title="世界观（5维度框架）" name="worldbuilding">
              <n-space vertical size="small">
                <n-card v-for="dim in wbDimensionCards" :key="dim.key" size="small" :title="dim.label">
                  <div class="dimension-fields">
                    <div v-for="(_val, key) in dim.data" :key="key" class="field-card field-card--editable">
                      <div class="field-card__title">{{ dimKeyLabels[key] || key }}</div>
                      <n-input
                        v-model:value="worldbuildingData[dim.key][key]"
                        type="textarea"
                        :autosize="{ minRows: 1, maxRows: 4 }"
                        size="small"
                      />
                    </div>
                  </div>
                </n-card>
              </n-space>
            </n-collapse-item>

            <n-collapse-item title="文风公约" name="style">
              <n-card size="small">
                <n-input
                  v-model:value="styleText"
                  type="textarea"
                  :autosize="{ minRows: 3, maxRows: 10 }"
                  placeholder="文风公约"
                />
              </n-card>
            </n-collapse-item>
          </n-collapse>
          <n-button secondary style="margin-top: 12px" @click="startBibleGeneration()">
            重新生成
          </n-button>
        </div>

        <!-- 初始状态 -->
        <div v-else class="step-info">
          <n-icon size="48" color="#18a058">
            <IconBook />
          </n-icon>
          <h3>准备生成世界观</h3>
          <p>AI 将分析您的故事创意，逐维度构建世界观和文风公约。</p>
          <n-button type="primary" style="margin-top: 16px" @click="startBibleGeneration()">
            开始生成
          </n-button>
        </div>
      </div>

      <!-- Step 2: Generate Characters (SSE) -->
      <div v-else-if="currentStep === 2" key="step2" class="step-panel">

        <n-alert v-if="charactersError" type="error" style="margin-bottom: 16px; width: 100%">
          {{ charactersError }}
        </n-alert>

        <!-- 生成中：逐个角色流式呈现 -->
        <div v-if="generatingCharacters && !charactersGenerated" class="step-generating">
          <div class="generating-header">
            <div class="generating-icon">
              <n-icon size="36" color="#2080f0">
                <IconPeople />
              </n-icon>
            </div>
            <div class="generating-text">
              <h3>{{ phaseMessage || '正在生成人物...' }}</h3>
              <p class="generating-sub">角色逐一呈现</p>
            </div>
          </div>

          <div class="streaming-cards">
            <!-- 已接收的角色 —— 完整卡片 -->
            <transition-group name="fade-slide">
              <div v-for="(char, idx) in streamingCharacters" :key="char.name || idx" class="char-card char-card--filled">
                <div class="char-card__header">
                  <div class="char-card__avatar" :class="char.role === '主角' ? 'char-card__avatar--protag' : ''">{{ char.name?.[0] || '?' }}</div>
                  <div class="char-card__title">
                    <span class="char-card__name">{{ char.name }}</span>
                    <n-tag size="small" :type="char.role === '主角' ? 'success' : 'default'" round>{{ char.role || '角色' }}</n-tag>
                  </div>
                </div>
                <div v-if="char.description" class="char-card__desc">{{ char.description }}</div>
                <div v-if="char.relationships && char.relationships.length" class="char-card__relations">
                  <n-tag v-for="(rel, ri) in char.relationships.slice(0, 3)" :key="ri" size="tiny" :bordered="false" type="info">
                    {{ typeof rel === 'string' ? rel : (rel.relation || rel.description || rel.target || '') }}
                  </n-tag>
                </div>
              </div>
            </transition-group>
            <!-- 当前正在生成的骨架位 —— 与卡片结构一致 -->
            <div class="char-card char-card--loading">
              <div class="char-card__header">
                <div class="char-card__avatar char-card__avatar--skeleton">
                  <span class="skeleton-dot__pulse"></span>
                </div>
                <div class="char-card__title">
                  <span class="char-card__skeleton-bar" style="width: 60px"></span>
                  <span class="char-card__skeleton-bar char-card__skeleton-bar--tag"></span>
                </div>
              </div>
              <div class="char-card__skeleton-body">
                <span class="char-card__skeleton-bar" style="width: 90%"></span>
                <span class="char-card__skeleton-bar" style="width: 70%"></span>
              </div>
            </div>

          </div>
        </div>

        <!-- 生成完成后显示可编辑预览 -->
        <div v-else-if="charactersGenerated" class="bible-preview">
          <n-alert type="success" title="人物生成完成" style="margin-bottom: 16px">
            请查看并修改角色设定，确认后将继续。
          </n-alert>
          <n-space vertical size="small" style="margin-bottom: 14px">
            <n-button
              size="small"
              type="primary"
              secondary
              :loading="bulkExtractingPsyche"
              :disabled="!editableCharacters.length"
              @click="runBulkCharacterExtract"
            >
              从简介填充空锚点（无模型）
            </n-button>
            <n-text depth="3" style="font-size: 11px; line-height: 1.5">
              与工作台「角色锚点」同一套 Bible 字段；仅填补仍为空的 T0 / 声线风格等，不覆盖已写内容。可在下方改完再点「确认修改并继续」落库。
            </n-text>
          </n-space>
          <n-list bordered>
            <n-list-item v-for="(char, idx) in editableCharacters" :key="idx">
              <div class="editable-character">
                <n-space vertical size="small" style="width: 100%">
                  <!-- 姓名 + 角色 + 删除 -->
                  <n-space :size="8" align="center" wrap>
                    <n-input v-model:value="char.name" size="small" style="width: 120px" placeholder="姓名" />
                    <n-button size="small" secondary @click="rollCharacterName(idx)">抽卡起名</n-button>
                    <n-input v-model:value="char.role" size="small" style="width: 100px" placeholder="角色定位" />
                    <n-button quaternary size="small" type="error" @click="editableCharacters.splice(idx, 1)">删除</n-button>
                  </n-space>
                  <!-- 简介 -->
                  <div class="editable-field">
                    <div class="editable-field__label">简介</div>
                    <n-input
                      v-model:value="char.description"
                      type="textarea"
                      :autosize="{ minRows: 1, maxRows: 4 }"
                      size="small"
                      placeholder="角色描述"
                    />
                  </div>
                  <!-- 心理状态 -->
                  <div v-if="char.mental_state" class="editable-field">
                    <div class="editable-field__label">心理状态</div>
                    <n-input v-model:value="char.mental_state" type="textarea" :autosize="{ minRows: 1, maxRows: 3 }" size="small" />
                  </div>
                  <!-- 口头禅 -->
                  <div v-if="char.verbal_tic" class="editable-field">
                    <div class="editable-field__label">口头禅</div>
                    <n-input v-model:value="char.verbal_tic" size="small" />
                  </div>
                  <!-- 习惯动作 -->
                  <div v-if="char.idle_behavior" class="editable-field">
                    <div class="editable-field__label">习惯动作</div>
                    <n-input v-model:value="char.idle_behavior" size="small" />
                  </div>
                  <!-- 人物关系 -->
                  <div v-if="char.relationships && char.relationships.length" class="editable-field">
                    <div class="editable-field__label">人物关系</div>
                    <n-space :size="4">
                      <n-tag v-for="(rel, ri) in char.relationships" :key="ri" size="small" :bordered="false">
                        {{ typeof rel === 'string' ? rel : (rel.relation || rel.description || rel.target || JSON.stringify(rel)) }}
                      </n-tag>
                    </n-space>
                  </div>
                  <!-- 公开人设 -->
                  <div v-if="char.public_profile" class="editable-field">
                    <div class="editable-field__label">公开人设</div>
                    <n-input v-model:value="char.public_profile" type="textarea" :autosize="{ minRows: 1, maxRows: 3 }" size="small" />
                  </div>
                  <!-- 隐藏身份 -->
                  <div v-if="char.hidden_profile" class="editable-field">
                    <div class="editable-field__label">隐藏身份</div>
                    <n-input v-model:value="char.hidden_profile" type="textarea" :autosize="{ minRows: 1, maxRows: 3 }" size="small" />
                  </div>
                </n-space>
              </div>
            </n-list-item>
          </n-list>
          <n-button secondary style="margin-top: 12px" @click="startCharactersGeneration()">
            重新生成
          </n-button>
        </div>

        <!-- 初始状态 -->
        <div v-else class="step-info">
          <n-icon size="48" color="#2080f0">
            <IconPeople />
          </n-icon>
          <h3>生成主要角色</h3>
          <p>基于已确认的世界观，AI 将生成主要角色及其关系。</p>
          <n-button type="primary" style="margin-top: 16px" @click="startCharactersGeneration()">
            开始生成
          </n-button>
        </div>
      </div>

      <!-- Step 3: Generate Locations (SSE) -->
      <div v-else-if="currentStep === 3" key="step3" class="step-panel">

        <n-alert v-if="locationsError" type="error" style="margin-bottom: 16px; width: 100%">
          {{ locationsError }}
        </n-alert>

        <!-- 生成中：骨架屏 + 流式数据 -->
        <div v-if="generatingLocations && !locationsGenerated" class="step-generating">
          <div class="generating-header">
            <div class="generating-icon">
              <n-icon size="36" color="#f0a020">
                <IconMap />
              </n-icon>
            </div>
            <div class="generating-text">
              <h3>{{ phaseMessage || '正在生成地图...' }}</h3>
              <p class="generating-sub">地点逐一呈现</p>
            </div>
          </div>

          <div class="streaming-loc-cards">
            <!-- 已接收的地点 —— 完整卡片 -->
            <transition-group name="fade-slide">
              <div v-for="(loc, idx) in streamingLocations" :key="loc.name || loc.id || idx" class="loc-card loc-card--filled">
                <div class="loc-card__header">
                  <div class="loc-card__icon">📍</div>
                  <div class="loc-card__title">
                    <span class="loc-card__name">{{ loc.name }}</span>
                    <n-tag size="small" type="info" round>{{ loc.type || loc.location_type || '地点' }}</n-tag>
                  </div>
                </div>
                <div v-if="loc.description" class="loc-card__desc">{{ loc.description }}</div>
              </div>
            </transition-group>
            <!-- 当前正在生成的骨架位 -->
            <div class="loc-card loc-card--loading">
              <div class="loc-card__header">
                <div class="loc-card__icon--skeleton"></div>
                <div class="loc-card__title">
                  <span class="loc-card__skeleton-bar" style="width: 70px"></span>
                  <span class="loc-card__skeleton-bar" style="width: 40px; height: 20px; border-radius: 10px"></span>
                </div>
              </div>
              <div class="loc-card__skeleton-body">
                <span class="loc-card__skeleton-bar" style="width: 85%"></span>
                <span class="loc-card__skeleton-bar" style="width: 60%"></span>
              </div>
            </div>

          </div>
        </div>

        <!-- 生成完成后显示可编辑预览 -->
        <div v-else-if="locationsGenerated" class="bible-preview">
          <n-alert type="success" title="地图生成完成" style="margin-bottom: 16px">
            请查看并修改地点设定，确认后将继续。
          </n-alert>
          <BibleLocationsGraphPreview :locations="bibleData.locations || []" />
          <n-list bordered style="margin-top: 16px">
            <n-list-item v-for="(loc, idx) in editableLocations" :key="loc.id || idx">
              <div class="editable-location">
                <n-space vertical size="small" style="width: 100%">
                  <n-space :size="8" align="center">
                    <n-input v-model:value="loc.name" size="small" style="width: 140px" placeholder="地点名" />
                    <n-input v-model:value="loc.location_type" size="small" style="width: 100px" placeholder="类型" />
                    <n-button quaternary size="small" type="error" @click="editableLocations.splice(idx, 1)">删除</n-button>
                  </n-space>
                  <n-input
                    v-model:value="loc.description"
                    type="textarea"
                    :autosize="{ minRows: 1, maxRows: 4 }"
                    size="small"
                    placeholder="地点描述"
                  />
                </n-space>
              </div>
            </n-list-item>
          </n-list>
          <n-button secondary style="margin-top: 12px" @click="startLocationsGeneration()">
            重新生成
          </n-button>
        </div>

        <!-- 初始状态 -->
        <div v-else class="step-info">
          <n-icon size="48" color="#f0a020">
            <IconMap />
          </n-icon>
          <h3>生成地图系统</h3>
          <p>基于已确认的世界观和人物，AI 将生成重要地点和地图结构。</p>
          <n-button type="primary" style="margin-top: 16px" @click="startLocationsGeneration()">
            开始生成
          </n-button>
        </div>
      </div>

      <!-- Step 4: 主线候选（LLM 推演） -->
      <div v-else-if="currentStep === 4" key="step4" class="step-panel step-panel--storyline">
        <n-alert
          v-if="step4RestoredFromCache"
          type="success"
          closable
          class="wizard-hint-alert"
          style="margin-bottom: 12px; width: 100%"
          @close="step4RestoredFromCache = false"
        >
          已恢复上次浏览时的<strong>主线候选</strong>与未提交的自定义文案（本地缓存，减少重复推演）。
        </n-alert>

        <div class="step-info step-info--wide">
          <n-icon size="48" color="#2080f0">
            <IconTimeline />
          </n-icon>
          <h3>确立故事主轴</h3>
          <p>基于你已确认的世界观、人物与地图，系统推演三条可选<strong>主线方向</strong>。选定一条即可落库为「主线」；支线留到工作台再养。</p>
        </div>

        <n-alert v-if="plotSuggestError" type="error" style="margin-bottom: 12px; width: 100%">
          {{ plotSuggestError }}
        </n-alert>
        <n-alert v-if="mainPlotCommitted" type="success" title="已保存主线" style="margin-bottom: 12px; width: 100%">
          已进入本书的主故事线记录，可随时在工作台「设置 → 故事线」中修改。
        </n-alert>

        <n-spin :show="plotSuggesting" style="width: 100%">
          <template #description>
            <span style="color: #999; font-size: 13px">AI 正在推演故事主线方向...</span>
          </template>

          <div v-if="plotSuggesting && !plotOptions.length" style="width: 100%">
            <WizardSkeleton type="storyline" />
          </div>

          <div v-if="!customMode" class="plot-options-block">
            <n-space vertical :size="12" style="width: 100%">
              <transition-group name="fade-slide">
                <n-card
                  v-for="opt in plotOptions"
                  :key="opt.id"
                  size="small"
                  :bordered="true"
                  class="plot-option-card"
                  :class="{ 'plot-option-card--disabled': mainPlotCommitted }"
                >
                  <template #header>
                    <n-space align="center" :size="8">
                      <n-tag size="small" type="info" round>{{ opt.type || '主线方案' }}</n-tag>
                      <span class="plot-option-title">{{ opt.title }}</span>
                    </n-space>
                  </template>
                  <n-space vertical :size="8">
                    <div class="plot-line"><strong>梗概：</strong>{{ opt.logline }}</div>
                    <div v-if="opt.core_conflict" class="plot-line"><strong>核心冲突：</strong>{{ opt.core_conflict }}</div>
                    <div v-if="opt.starting_hook" class="plot-line"><strong>开篇钩子：</strong>{{ opt.starting_hook }}</div>
                    <n-button
                      type="primary"
                      size="small"
                      :loading="adoptingPlotId === opt.id"
                      :disabled="mainPlotCommitted"
                      @click="adoptPlotOption(opt)"
                    >
                      选这条作为主线
                    </n-button>
                  </n-space>
                </n-card>
              </transition-group>
            </n-space>

            <n-space style="margin-top: 16px; width: 100%" justify="center" :size="12">
              <n-button secondary :disabled="mainPlotCommitted || plotSuggesting" @click="refreshPlotSuggestions">
                换一组方向
              </n-button>
              <n-button secondary :disabled="mainPlotCommitted" @click="customMode = true">
                我有自己的想法
              </n-button>
            </n-space>
          </div>

          <div v-else class="plot-custom-block">
            <n-input
              v-model:value="customLogline"
              type="textarea"
              placeholder="用一句话写下你想写的主线（例如：废柴少年为救妹妹卷入财阀灵根黑市……）"
              :autosize="{ minRows: 2, maxRows: 5 }"
              :disabled="mainPlotCommitted"
            />
            <n-space style="margin-top: 12px" :size="8">
              <n-button :disabled="mainPlotCommitted" @click="cancelCustomMainPlot">返回候选</n-button>
              <n-button
                type="primary"
                :loading="adoptingCustom"
                :disabled="mainPlotCommitted"
                @click="adoptCustomMainPlot"
              >
                用这句话作为主线
              </n-button>
            </n-space>
          </div>
        </n-spin>
      </div>

      <!-- Step 5: Plot Arc -->
      <div v-else-if="currentStep === 5" key="step5" class="step-panel">
        <div class="step-info">
          <n-icon size="48" color="#f0a020">
            <IconChart />
          </n-icon>
          <h3>设计情节弧线</h3>
          <p>规划故事的起承转合，设置关键剧情点和张力变化。</p>
          <n-space vertical size="small" style="margin-top: 16px; text-align: left">
            <div>• 开端：故事的起点</div>
            <div>• 上升：矛盾逐渐激化</div>
            <div>• 转折：关键转折点</div>
            <div>• 高潮：矛盾最激烈时刻</div>
            <div>• 结局：故事的收尾</div>
          </n-space>
        </div>
      </div>

      <!-- Step 6: Complete -->
      <div v-else-if="currentStep === 6" key="step6" class="step-panel">
        <div class="step-info">
          <n-icon size="48" color="#18a058">
            <IconCheck />
          </n-icon>
          <h3>准备就绪！</h3>
          <p>所有基础设置已完成，现在可以开始创作了。</p>
          <p style="margin-top: 12px; color: var(--app-text-muted)">您可以随时在工作台的"设置"面板中调整这些内容。</p>
        </div>
      </div>
    </div>

    <template #footer>
      <n-space justify="space-between" style="width: 100%">
        <n-space>
          <n-button v-if="currentStep > 1 && currentStep < 6" @click="handlePrev">
            返回上一步
          </n-button>
          <n-button v-if="currentStep > 1 && currentStep < 6" @click="handleSkip" style="margin-left: 8px">
            跳过向导
          </n-button>
        </n-space>
        <n-space>
          <!-- 步骤1~3：已生成后显示"确认修改并继续" -->

          <n-button
            v-if="(currentStep === 1 && bibleGenerated) || (currentStep === 2 && charactersGenerated) || (currentStep === 3 && locationsGenerated)"
            type="primary"
            :loading="savingStep"
            @click="handleNext"
          >
            确认修改并继续
          </n-button>
          <!-- 步骤4：选了主线后可下一步 -->
          <n-button v-if="currentStep === 4" :disabled="!mainPlotCommitted" @click="handleNext"> 下一步 </n-button>
          <!-- 步骤5：进入工作台 -->
          <n-button v-if="currentStep === 5" type="primary" @click="handleComplete">
            进入工作台
          </n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { h, ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { bibleApi, type BibleDTO, type BibleRelationshipEntry, type CharacterDTO, type StyleNoteDTO, consumeBibleGenerateStream, type WorldbuildingDimensionData } from '@/api/bible'
import { worldbuildingApi } from '@/api/worldbuilding'
import { workflowApi, type MainPlotOptionDTO } from '@/api/workflow'
import { characterPsycheApi } from '@/api/engineCore'
import { resolveHttpUrl } from '@/api/config'
import BibleLocationsGraphPreview from './BibleLocationsGraphPreview.vue'
import WizardSkeleton from './WizardSkeleton.vue'
import {
  clearWizardUiCache,
  isPlotOptionsCacheFresh,
  markWizardCompleted,
  readWizardUiCache,
  setWizardLastStep,
  writeWizardUiCache,
  type WizardUiCachePayload,
} from '@/utils/wizardStageCache'
import { drawGachaFullName } from '@/utils/characterNameGacha'

// --- 图标组件 (SVG 手写版) ---
const IconBook = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', width: '1em', height: '1em' },
    h('path', { fill: 'currentColor', d: 'M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z' }))

const IconPeople = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', width: '1em', height: '1em' },
    h('path', { fill: 'currentColor', d: 'M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z' }))

const IconMap = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', width: '1em', height: '1em' },
    h('path', { fill: 'currentColor', d: 'M20.5 3l-.16.03L15 5.1L9 3L3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1l5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5zM15 19l-6-2.11V5l6 2.11V19z' }))

const IconTimeline = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', width: '1em', height: '1em' },
    h('path', { fill: 'currentColor', d: 'M13 3c-4.97 0-9 4.03-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42C8.27 19.99 10.51 21 13 21c4.97 0 9-4.03 9-9s-4.03-9-9-9zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z' }))

const IconChart = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', width: '1em', height: '1em' },
    h('path', { fill: 'currentColor', d: 'M5 19h14v2H5zM19 17h2v-4h-2v4zM15 17h2V7h-2v10zM11 17h2v-7h-2v7zM7 17h2v-3H7v3zM3 17h2v-6H3v6z' }))

const IconCheck = () =>
  h('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', width: '1em', height: '1em' },
    h('path', { fill: 'currentColor', d: 'M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z' }))

const WB_DIMS = ['core_rules', 'geography', 'society', 'culture', 'daily_life'] as const

/** 世界观维度 key → 中文标签 */
const dimKeyLabels: Record<string, string> = {
  power_system: '力量体系',
  physics_rules: '物理规律',
  magic_tech: '魔法/科技',
  cost_and_limitation: '代价与限制',
  resource_scarcity: '稀缺资源',
  terrain: '地形',
  climate: '气候',
  resources: '资源',
  ecology: '生态',
  forbidden_zones: '禁区',
  urban_core: '核心城市',
  hidden_realms: '秘境',
  politics: '政治',
  economy: '经济',
  class_system: '阶级',
  power_structure: '权力结构',
  oppression_mechanism: '压迫机制',
  class_division: '阶层划分',
  history: '历史',
  religion: '宗教',
  taboos: '禁忌',
  worship: '崇拜与祭祀',
  oaths_and_curses: '誓言与诅咒',
  food_clothing: '衣食住行',
  language_slang: '俚语口音',
  entertainment: '娱乐方式',
  survival_tactics: '生存策略',
  market_reality: '市场真相',
  food_and_drink: '饮食文化',
  slang_and_profanity: '黑话粗话',
}

function emptyWorldbuildingShape(): Record<(typeof WB_DIMS)[number], Record<string, string>> {
  return {
    core_rules: {},
    geography: {},
    society: {},
    culture: {},
    daily_life: {},
  }
}

function createEmptyBible(): BibleDTO {
  return {
    id: '',
    novel_id: '',
    characters: [],
    world_settings: [],
    locations: [],
    timeline_notes: [],
    style_notes: [],
  }
}

function worldbuildingFromWorldSettings(
  settings: { name: string; description?: string }[] | undefined
): Record<(typeof WB_DIMS)[number], Record<string, string>> {
  const out = emptyWorldbuildingShape()
  const dimSet = new Set<string>(WB_DIMS)
  for (const s of settings || []) {
    const dot = s.name.indexOf('.')
    if (dot < 0) continue
    const dim = s.name.slice(0, dot)
    const key = s.name.slice(dot + 1)
    if (!dimSet.has(dim) || !key) continue
    out[dim as (typeof WB_DIMS)[number]][key] = (s.description || '').trim()
  }
  return out
}

function normalizeWorldbuildingFromApi(raw: Record<string, unknown> | null | undefined) {
  const out = emptyWorldbuildingShape()
  if (!raw || typeof raw !== 'object') return out
  for (const d of WB_DIMS) {
    const block = raw[d]
    if (block && typeof block === 'object') {
      out[d] = { ...(block as Record<string, string>) }
    }
  }
  return out
}

function mergeWorldbuildingDisplay(
  fromApi: ReturnType<typeof normalizeWorldbuildingFromApi>,
  fromBibleSettings: ReturnType<typeof worldbuildingFromWorldSettings>
) {
  const out = emptyWorldbuildingShape()
  for (const d of WB_DIMS) {
    const merged = { ...fromBibleSettings[d], ...fromApi[d] }
    out[d] = merged
  }
  return out
}

const props = withDefaults(
  defineProps<{
    novelId: string
    show: boolean
    targetChapters?: number
  }>(),
  { targetChapters: 100 }
)

const message = useMessage()
const dialog = useDialog()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'complete'): void
  (e: 'skip'): void
}>()

/** 增量 JSON 解析器：从流式文本中提取已完成和正在流式的字段 */
function parseStreamingJsonFields(text: string): {
  completed: Record<string, string>
  streamingKey: string
  streamingValue: string
} {
  const result: { completed: Record<string, string>; streamingKey: string; streamingValue: string } = {
    completed: {},
    streamingKey: '',
    streamingValue: '',
  }

  if (!text) return result

  // 提取 JSON 内容（去除 markdown 代码块标记）
  let jsonStr = text
  const jsonMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/)
  if (jsonMatch) {
    jsonStr = jsonMatch[1]
  }
  // 尝试提取 { ... } 部分
  const braceStart = jsonStr.indexOf('{')
  if (braceStart === -1) return result
  jsonStr = jsonStr.slice(braceStart)

  // 用正则逐个匹配 "key": "value" 对
  const completedRe = /"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)"/g
  let m: RegExpExecArray | null
  while ((m = completedRe.exec(jsonStr)) !== null) {
    result.completed[m[1]] = m[2]
      .replace(/\\n/g, '\n')
      .replace(/\\t/g, '\t')
      .replace(/\\"/g, '"')
      .replace(/\\\\/g, '\\')
  }

  // 正在流式的字段
  const streamingRe = /"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)$/
  const streamMatch = streamingRe.exec(jsonStr)
  if (streamMatch) {
    if (!(streamMatch[1] in result.completed)) {
      result.streamingKey = streamMatch[1]
      result.streamingValue = streamMatch[2]
        .replace(/\\n/g, '\n')
        .replace(/\\t/g, '\t')
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, '\\')
    }
  }

  return result
}

const modalOpen = computed({
  get: () => props.show,
  set: (v: boolean) => {
    if (v) {
      emit('update:show', true)
      return
    }
    requestClose()
  },
})

const currentStep = ref(1)
const stepStatus = ref<'process' | 'finish' | 'error' | 'wait'>('process')
const resumedFromStep = ref(0)

// ── 第1步：SSE 流式生成世界观 ──
const generatingBible = ref(false)
const bibleGenerated = ref(false)
const bibleError = ref('')
const bibleData = ref<BibleDTO>(createEmptyBible())
const worldbuildingData = ref<ReturnType<typeof emptyWorldbuildingShape>>(emptyWorldbuildingShape())
const styleText = ref('')

/** SSE 流式状态 */
const phaseMessage = ref('')
const activeDimension = ref('')
const completedDimensions = ref<Set<string>>(new Set())
const activeField = ref('')
const arrivedFields = ref<Set<string>>(new Set())
const streamingDimText = ref('')
const sseAbortController = ref<AbortController | null>(null)

/** 世界观维度卡片 */
const wbDimensionCards = computed(() => {
  const labels: Record<string, string> = {
    core_rules: '核心法则',
    geography: '地理生态',
    society: '社会结构',
    culture: '历史文化',
    daily_life: '沉浸感细节',
  }
  return WB_DIMS.map(key => ({ key, label: labels[key], data: worldbuildingData.value[key] }))
})

// ── 第2步：SSE 流式生成人物 ──
const generatingCharacters = ref(false)
const charactersGenerated = ref(false)
const charactersError = ref('')
const streamingCharacters = ref<Array<{ name: string; role: string; description: string; relationships: BibleRelationshipEntry[] }>>([])
const charactersSseAbort = ref<AbortController | null>(null)

/** 可编辑的人物列表 */
interface EditableCharacter {
  id: string
  name: string
  role: string
  description: string
  mental_state: string
  verbal_tic: string
  idle_behavior: string
  relationships: BibleRelationshipEntry[]
  public_profile: string
  hidden_profile: string
}

/** 从 CharacterDTO 映射到 EditableCharacter */
function mapCharacterToEditable(c: CharacterDTO): EditableCharacter {
  let role = c.role || ''
  let desc = c.description || ''
  if (!role && desc.includes(' - ')) {
    const sepIdx = desc.indexOf(' - ')
    role = desc.slice(0, sepIdx).trim()
    desc = desc.slice(sepIdx + 3).trim()
  }
  return {
    id: c.id || '',
    name: c.name || '',
    role,
    description: desc,
    mental_state: c.mental_state || '',
    verbal_tic: c.verbal_tic || '',
    idle_behavior: c.idle_behavior || '',
    relationships: c.relationships || [],
    public_profile: c.public_profile || '',
    hidden_profile: c.hidden_profile || '',
  }
}

const editableCharacters = ref<EditableCharacter[]>([])

/** 引导页第 2 步：随机起名 */
function rollCharacterName(idx: number) {
  const row = editableCharacters.value[idx]
  if (!row) return
  const taken = new Set<string>()
  for (let i = 0; i < editableCharacters.value.length; i++) {
    if (i === idx) continue
    const n = editableCharacters.value[i]?.name?.trim()
    if (n) taken.add(n)
  }
  row.name = drawGachaFullName(taken)
  message.success('已抽卡起名')
}

// ── 第3步：SSE 流式生成地点 ──
const generatingLocations = ref(false)
const locationsGenerated = ref(false)
const locationsError = ref('')
const locationPollTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const characterPollTimer = ref<ReturnType<typeof setTimeout> | null>(null)

/** 作废第 2/3 步后台轮询 */
const step2PollEpoch = ref(0)
const step3PollEpoch = ref(0)
const isProcessingNext = ref(false)

/**
 * 核心：同步当前小说的生成状态
 */
async function syncGenerationState() {
  if (!props.novelId || !props.show) return

  try {
    const bible = await bibleApi.getBible(props.novelId)
    bibleData.value = bible

    if (bible.world_settings && bible.world_settings.length > 0) {
      bibleGenerated.value = true
      let fromApi = emptyWorldbuildingShape()
      try {
        const w = await worldbuildingApi.getWorldbuilding(props.novelId)
        fromApi = normalizeWorldbuildingFromApi(w as unknown as Record<string, unknown>)
      } catch { /* ignore */ }
      const fromWs = worldbuildingFromWorldSettings(bible.world_settings)
      worldbuildingData.value = mergeWorldbuildingDisplay(fromApi, fromWs)
    }

    if (bible.characters && bible.characters.length > 0) {
      charactersGenerated.value = true
      generatingCharacters.value = false
      editableCharacters.value = bible.characters.map(mapCharacterToEditable)
    }

    if (bible.locations && bible.locations.length > 0) {
      locationsGenerated.value = true
      generatingLocations.value = false
      editableLocations.value = bible.locations.map(loc => ({
        id: loc.id,
        name: loc.name,
        location_type: loc.location_type || (loc as any).type || '地点',
        description: loc.description || ''
      }))
    }
  } catch (error) {
    console.warn('[NovelSetupGuide] Failed to sync state:', error)
  }
}

const streamingLocations = ref<Array<{ name: string; id?: string; type?: string; location_type?: string; description: string }>>([])
const locationsSseAbort = ref<AbortController | null>(null)
/** 可编辑的地点列表 */
const editableLocations = ref<Array<{ name: string; id?: string; location_type?: string; description: string }>>([])

// ── Step 4：主线推演 ──
const plotOptions = ref<MainPlotOptionDTO[]>([])
const plotSuggesting = ref(false)
const plotSuggestError = ref('')
const mainPlotCommitted = ref(false)
const customMode = ref(false)
const customLogline = ref('')
const adoptingPlotId = ref<string | null>(null)
const adoptingCustom = ref(false)
const step4RestoredFromCache = ref(false)

const chapterEndForStoryline = computed(() => Math.max(1, props.targetChapters ?? 100))

function persistStepFourUiToCache(opts?: { includePlotOptions?: boolean }) {
  if (currentStep.value !== 4) return
  const patch: Partial<Omit<WizardUiCachePayload, 'v' | 'novelId'>> = {
    customMode: customMode.value,
    customLogline: customLogline.value,
  }
  if (opts?.includePlotOptions) {
    patch.plotOptions = plotOptions.value.length ? plotOptions.value : undefined
  }
  writeWizardUiCache(props.novelId, patch)
}

async function loadPlotSuggestions() {
  step4RestoredFromCache.value = false
  plotSuggesting.value = true
  plotSuggestError.value = ''
  try {
    const res = await workflowApi.suggestMainPlotOptions(props.novelId)
    plotOptions.value = res.plot_options || []
    if (plotOptions.value.length) {
      writeWizardUiCache(props.novelId, { plotOptions: plotOptions.value })
    }
  } catch (e: unknown) {
    plotSuggestError.value = '推演失败，请重试'
  } finally {
    plotSuggesting.value = false
  }
}

async function refreshPlotSuggestions() {
  await loadPlotSuggestions()
}

async function adoptPlotOption(opt: MainPlotOptionDTO) {
  adoptingPlotId.value = opt.id
  try {
    const parts = [
      opt.logline,
      opt.core_conflict ? `核心冲突：${opt.core_conflict}` : '',
      opt.starting_hook ? `开篇钩子：${opt.starting_hook}` : '',
    ].filter(Boolean)
    await workflowApi.createStoryline(props.novelId, {
      storyline_type: 'main_plot',
      estimated_chapter_start: 1,
      estimated_chapter_end: chapterEndForStoryline.value,
      name: opt.title.slice(0, 200),
      description: parts.join('\n\n').slice(0, 8000),
    })
    mainPlotCommitted.value = true
    clearWizardUiCache(props.novelId)
    message.success('主线已保存')
  } catch (e: unknown) {
    message.error('保存失败')
  } finally {
    adoptingPlotId.value = null
  }
}

async function adoptCustomMainPlot() {
  const t = customLogline.value.trim()
  if (!t) {
    message.warning('请先写下一句话主线')
    return
  }
  adoptingCustom.value = true
  try {
    await workflowApi.createStoryline(props.novelId, {
      storyline_type: 'main_plot',
      estimated_chapter_start: 1,
      estimated_chapter_end: chapterEndForStoryline.value,
      name: t.length > 80 ? `${t.slice(0, 80)}…` : t,
      description: t.slice(0, 8000),
    })
    mainPlotCommitted.value = true
    customMode.value = false
    clearWizardUiCache(props.novelId)
    message.success('主线已保存')
  } catch (e: unknown) {
    message.error('保存失败')
  } finally {
    adoptingCustom.value = false
  }
}

function cancelCustomMainPlot() {
  customMode.value = false
  persistStepFourUiToCache()
}

function hydrateStepFourFromCache() {
  step4RestoredFromCache.value = false
  const cached = readWizardUiCache(props.novelId)
  if (!cached) return
  if (cached.customMode != null) customMode.value = cached.customMode
  if (cached.customLogline != null) customLogline.value = cached.customLogline
  if (isPlotOptionsCacheFresh(cached) && cached.plotOptions?.length) {
    plotOptions.value = cached.plotOptions
    step4RestoredFromCache.value = true
    return
  }
}

// ════════════════════════════════════════════════════════════════════════════
// SSE 流式生成函数
// ════════════════════════════════════════════════════════════════════════════

const sseAvailable = ref<boolean | null>(null)

async function checkSseAvailable(novelId: string): Promise<boolean> {
  if (sseAvailable.value !== null) return sseAvailable.value
  try {
    const url = resolveHttpUrl(`/api/v1/bible/novels/${novelId}/generate-stream?stage=worldbuilding`)
    const res = await fetch(url, { method: 'HEAD', signal: AbortSignal.timeout(5000) })
    const ok = res.ok || res.status === 405
    sseAvailable.value = ok
    return ok
  } catch {
    sseAvailable.value = true
    return true
  }
}

const pollTimerRef = ref<ReturnType<typeof setTimeout> | null>(null)
const biblePollEpoch = ref(0)

function clearGenerationTimers() {
  if (pollTimerRef.value != null) {
    clearTimeout(pollTimerRef.value)
    pollTimerRef.value = null
  }
  if (characterPollTimer.value != null) {
    clearTimeout(characterPollTimer.value)
    characterPollTimer.value = null
  }
  if (locationPollTimer.value != null) {
    clearTimeout(locationPollTimer.value)
    locationPollTimer.value = null
  }
}

function pollBibleUntil(
  predicate: (bible: BibleDTO) => boolean,
  options: {
    isStale: () => boolean
    onSuccess: () => void
    onFatal: (message: string) => void
  },
): void {
  const tick = async () => {
    if (options.isStale()) return
    try {
      const bible = await bibleApi.getBible(props.novelId)
      if (options.isStale()) return
      bibleData.value = bible
      if (predicate(bible)) { options.onSuccess(); return }
    } catch (err: unknown) {
      if (options.isStale()) return
      options.onFatal('查询 Bible 失败')
      return
    }
    window.setTimeout(() => { void tick() }, 2000)
  }
  void tick()
}

async function startBibleGenerationPoll() {
  clearGenerationTimers()
  biblePollEpoch.value += 1
  const epoch = biblePollEpoch.value
  generatingBible.value = true
  bibleGenerated.value = false
  bibleError.value = ''
  phaseMessage.value = '正在生成世界观...'

  try {
    await bibleApi.generateBible(props.novelId, 'worldbuilding')
    const runPoll = async () => {
      if (biblePollEpoch.value !== epoch || !generatingBible.value) return
      try {
        const status = await bibleApi.getBibleStatus(props.novelId)
        if (status.ready) {
          clearGenerationTimers()
          generatingBible.value = false
          phaseMessage.value = ''
          completedDimensions.value = new Set(WB_DIMS)
          bibleGenerated.value = true
          syncGenerationState()
          return
        }
      } catch (error: unknown) {
        if (biblePollEpoch.value !== epoch) return
        clearGenerationTimers()
        generatingBible.value = false
        bibleError.value = '检查状态失败'
        phaseMessage.value = ''
        return
      }
      pollTimerRef.value = window.setTimeout(() => { void runPoll() }, 2000)
    }
    runPoll()
  } catch (error: unknown) {
    generatingBible.value = false
    bibleError.value = '生成失败，请重试'
    phaseMessage.value = ''
  }
}

async function startBibleGeneration() {
  try {
    const useSse = await checkSseAvailable(props.novelId)
    if (useSse) {
      startBibleGenerationSSE()
    } else {
      startBibleGenerationPoll()
    }
  } catch {
    startBibleGenerationSSE()
  }
}

function startBibleGenerationSSE() {
  generatingBible.value = true
  bibleGenerated.value = false
  bibleError.value = ''
  phaseMessage.value = '正在准备生成环境...'
  activeDimension.value = ''
  completedDimensions.value = new Set()
  activeField.value = ''
  arrivedFields.value = new Set()
  streamingDimText.value = ''
  worldbuildingData.value = emptyWorldbuildingShape()
  styleText.value = ''

  const ctrl = new AbortController()
  sseAbortController.value = ctrl

  consumeBibleGenerateStream(props.novelId, 'worldbuilding', {
    signal: ctrl.signal,
    onPhase: (phase, msg) => {
      phaseMessage.value = msg
      if (phase.startsWith('worldbuilding_') && phase !== 'worldbuilding_done') {
        const dimKey = phase.replace('worldbuilding_', '')
        if (WB_DIMS.includes(dimKey as typeof WB_DIMS[number])) {
          if (activeDimension.value && activeDimension.value !== dimKey) {
            completedDimensions.value = new Set([...completedDimensions.value, activeDimension.value])
          }
          activeDimension.value = dimKey
          activeField.value = ''
          arrivedFields.value = new Set()
          streamingDimText.value = ''
        }
      }
      if (phase === 'worldbuilding_done') {
        completedDimensions.value = new Set(WB_DIMS)
        activeDimension.value = ''
      }
    },
    onStyle: (content) => {
      styleText.value = content
    },
    onWorldbuildingDimChunk: (dimension, chunk) => {
      streamingDimText.value += chunk
      if (activeDimension.value !== dimension) {
        if (activeDimension.value) {
          completedDimensions.value = new Set([...completedDimensions.value, activeDimension.value])
        }
        activeDimension.value = dimension
      }
      const parsed = parseStreamingJsonFields(streamingDimText.value)
      const dim = dimension as keyof typeof worldbuildingData.value
      const completedFields: Record<string, string> = { ...parsed.completed }
      if (parsed.streamingKey) {
        completedFields[parsed.streamingKey] = parsed.streamingValue
        activeField.value = parsed.streamingKey
      }
      worldbuildingData.value[dim] = { ...worldbuildingData.value[dim], ...completedFields }
    },
    onDone: () => {
      completedDimensions.value = new Set(WB_DIMS)
      activeDimension.value = ''
      generatingBible.value = false
      bibleGenerated.value = true
      syncGenerationState()
    },
    onError: (msg) => {
      startBibleGenerationPoll()
    },
  })
}

async function startCharactersGeneration() {
  generatingCharacters.value = true
  charactersGenerated.value = false
  charactersError.value = ''
  streamingCharacters.value = []
  
  const ctrl = new AbortController()
  charactersSseAbort.value = ctrl

  consumeBibleGenerateStream(props.novelId, 'characters', {
    signal: ctrl.signal,
    onPhase: (phase, msg) => { phaseMessage.value = msg },
    onCharacter: (char) => {
      streamingCharacters.value.push(char)
    },
    onDone: () => {
      generatingCharacters.value = false
      charactersGenerated.value = true
      syncGenerationState()
    },
    onError: (msg) => {
      generatingCharacters.value = false
      charactersError.value = msg
    }
  })
}

async function startLocationsGeneration() {
  generatingLocations.value = true
  locationsGenerated.value = false
  locationsError.value = ''
  streamingLocations.value = []

  const ctrl = new AbortController()
  locationsSseAbort.value = ctrl

  consumeBibleGenerateStream(props.novelId, 'locations', {
    signal: ctrl.signal,
    onPhase: (phase, msg) => { phaseMessage.value = msg },
    onLocation: (loc) => {
      streamingLocations.value.push(loc)
    },
    onDone: () => {
      generatingLocations.value = false
      locationsGenerated.value = true
      syncGenerationState()
    },
    onError: (msg) => {
      generatingLocations.value = false
      locationsError.value = msg
    }
  })
}

const handleNext = async () => {
  if (currentStep.value < 6) {
    currentStep.value++
    if (currentStep.value === 4) hydrateStepFourFromCache()
  }
}

const handlePrev = () => {
  if (currentStep.value > 1) currentStep.value--
}

const handleSkip = () => {
  emit('skip')
}

const handleComplete = () => {
  markWizardCompleted(props.novelId)
  emit('complete')
}

const requestClose = () => {
  if (generatingBible.value || generatingCharacters.value || generatingLocations.value) {
    dialog.warning({
      title: '正在生成中',
      content: '关闭窗口不会中断后台生成，但您将无法实时看到进度。确定关闭吗？',
      positiveText: '确定关闭',
      negativeText: '取消',
      onPositiveClick: () => { emit('update:show', false) }
    })
  } else {
    emit('update:show', false)
  }
}

onMounted(() => {
  syncGenerationState()
})

onUnmounted(() => {
  clearGenerationTimers()
  sseAbortController.value?.abort()
  charactersSseAbort.value?.abort()
  locationsSseAbort.value?.abort()
})
</script>

<style scoped>
.wizard-steps { margin-bottom: 24px; }
.step-content { min-height: 400px; }
.step-panel { display: flex; flex-direction: column; align-items: center; }
.step-generating { width: 100%; }
.generating-header { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.streaming-cursor { display: inline-block; width: 2px; height: 1.2em; background: var(--n-primary-color); margin-left: 2px; animation: blink 1s infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
.char-card, .loc-card { margin-bottom: 12px; border: 1px solid var(--n-border-color); border-radius: 8px; padding: 12px; }
.fade-slide-enter-active, .fade-slide-leave-active { transition: all 0.5s ease; }
.fade-slide-enter-from, .fade-slide-leave-to { opacity: 0; transform: translateY(20px); }
</style>
