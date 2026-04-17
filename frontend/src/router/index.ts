import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Workbench from '../views/Workbench.vue'
import Chapter from '../views/Chapter.vue'
import Cast from '../views/Cast.vue'
import CharacterGraph from '../views/CharacterGraph.vue'
import LocationGraph from '../views/LocationGraph.vue'
import CharacterSchedulerSimulator from '../components/debug/CharacterSchedulerSimulator.vue'

// Renaissance Shadow System Views
import RenaissanceHome from '../views/renaissance/HomeView.vue'
// The following will be created in the next steps
// import RenaissanceOnboarding from '../views/renaissance/OnboardingView.vue'
// import RenaissanceWorkbench from '../views/renaissance/WorkbenchView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'Home', component: Home },
    
    // Renaissance (Visual Sovereignty) Group
    { path: '/renaissance/home', name: 'RenaissanceHome', component: RenaissanceHome },
    { 
      path: '/renaissance/onboarding', 
      name: 'RenaissanceOnboarding', 
      component: () => import('../views/renaissance/OnboardingView.vue') 
    },
    { 
      path: '/renaissance/workbench/:slug', 
      name: 'RenaissanceWorkbench', 
      component: () => import('../views/renaissance/WorkbenchView.vue') 
    },

    { path: '/book/:slug/workbench', name: 'Workbench', component: Workbench },
    { path: '/book/:slug/cast', name: 'Cast', component: Cast },
    { path: '/book/:slug/chapter/:id', name: 'Chapter', component: Chapter },
    { path: '/book/:slug/characters', name: 'CharacterGraph', component: CharacterGraph },
    { path: '/book/:slug/location-graph', name: 'LocationGraph', component: LocationGraph },
    { path: '/debug/scheduler', name: 'CharacterSchedulerSimulator', component: CharacterSchedulerSimulator },
  ],
})

export default router
